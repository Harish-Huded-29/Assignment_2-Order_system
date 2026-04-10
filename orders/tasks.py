# orders/tasks.py

from .logger import (
    log_status_transition, log_step_started, log_step_success,
    log_step_failed, log_order_completed, log_order_failed,
    log_inventory_deducted, log_inventory_insufficient,
)
import logging
import razorpay
from celery import shared_task
from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# RAZORPAY PAYMENT FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def create_razorpay_order(amount_paise, order_id):
    """
    Creates a Razorpay order object.

    WHY create a Razorpay order first?
    Razorpay's flow works like this:
    1. Your backend creates a "Razorpay order" with the amount
    2. Frontend uses that order ID to show the payment popup
    3. Customer pays
    4. Razorpay sends confirmation back

    amount_paise = amount in smallest currency unit (paise for INR)
    So Rs. 100 = 10000 paise

    In test mode, no real money moves.
    """
    client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )

    razorpay_order = client.order.create({
        'amount':   amount_paise,
        'currency': 'INR',
        'receipt':  f'order_{order_id}',
        'notes': {
            'order_system_id': str(order_id)
        }
    })

    logger.info(f"[{order_id}] Razorpay order created: {razorpay_order['id']}")
    return razorpay_order


def verify_razorpay_payment(razorpay_order_id, razorpay_payment_id, razorpay_signature):
    """
    Verifies that a payment actually happened and wasn't faked.

    Razorpay sends back 3 values after payment:
    - razorpay_order_id    → the order we created
    - razorpay_payment_id  → the actual payment transaction
    - razorpay_signature   → a hash to prove it's genuine

    We verify the signature using our secret key.
    If verification fails → payment was tampered with → reject it.
    """
    client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )

    try:
        client.utility.verify_payment_signature({
            'razorpay_order_id':   razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature':  razorpay_signature,
        })
        logger.info(f"Payment verified: {razorpay_payment_id}")
        return True
    except razorpay.errors.SignatureVerificationError:
        logger.error(f"Payment signature verification FAILED: {razorpay_payment_id}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# INVENTORY CHECK WITH LOCKING — THE CONCURRENCY SOLUTION
# ─────────────────────────────────────────────────────────────────────────────

def check_and_deduct_inventory(order_id, items):
    """
    Checks inventory and deducts stock atomically.

    This is the most important function for the concurrency requirement.

    WHY transaction.atomic()?
    Everything inside this block is one database transaction.
    If anything fails halfway through (e.g. after deducting burger
    but before deducting fries), the entire thing is rolled back.
    The database is never left in a half-updated state.

    WHY select_for_update()?
    This generates SQL: SELECT * FROM inventory WHERE ... FOR UPDATE
    The FOR UPDATE part tells PostgreSQL: "lock this row."
    Any other transaction trying to read this row will WAIT
    until we finish. This prevents two workers from both reading
    quantity=5 and both thinking they can proceed.

    This is the correct solution to the race condition.
    Application-level locks (Python locks, Redis locks) are NOT
    sufficient because multiple worker processes on different
    machines can't share Python memory.
    Only the database can coordinate across all workers.
    """
    with transaction.atomic():
        insufficient = []

        for item in items:
            item_name = item['name'].lower()
            quantity_needed = item['quantity']

            try:
                # select_for_update() LOCKS this row until transaction ends
                # No other worker can read or write this row until we're done
                inventory = (
                    __import__('orders.models', fromlist=['Inventory'])
                    .Inventory.objects
                    .select_for_update()  # ← THE LOCK
                    .get(item_name=item_name)
                )
            except Exception:
                logger.warning(
                    f"[{order_id}] Item '{item_name}' not found in inventory"
                )
                insufficient.append(
                    f"{item_name} (not in inventory)"
                )
                continue

            if inventory.quantity < quantity_needed:
                # Not enough stock — add to insufficient list
                insufficient.append(
                    f"{item_name} "
                    f"(need {quantity_needed}, have {inventory.quantity})"
                )
                log_inventory_insufficient(
                    order_id, item_name,
                    quantity_needed, inventory.quantity
                )
            else:
                # Enough stock — deduct it
                inventory.quantity -= quantity_needed
                inventory.save(update_fields=['quantity', 'updated_at'])
                log_inventory_deducted(
                    order_id, item_name,
                    quantity_needed, inventory.quantity
                )
        if insufficient:
            # Something wasn't available — raise exception
            # transaction.atomic() will roll back ALL deductions made so far
            raise Exception(
                f"Insufficient inventory: {', '.join(insufficient)}"
            )

    # If we reach here, all items were available and deducted successfully
    logger.info(f"[{order_id}] All inventory deducted successfully")


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS (same as Day 4)
# ─────────────────────────────────────────────────────────────────────────────

def update_step_metadata(order, step_name, status, error=None):
    metadata = order.retry_metadata or {}
    step_data = metadata.get(step_name, {'attempts': 0, 'last_error': None})
    step_data['attempts'] += 1
    step_data['status'] = status
    step_data['last_error'] = error
    metadata[step_name] = step_data
    order.retry_metadata = metadata
    order.save(update_fields=['retry_metadata', 'updated_at'])
    logger.info(
        f"[{order.id}] Step '{step_name}' → {status} "
        f"(attempt {step_data['attempts']})"
        + (f" | {error}" if error else "")
    )


def step_already_completed(order, step_name):
    metadata = order.retry_metadata or {}
    done = metadata.get(step_name, {}).get('status') == 'success'
    if done:
        logger.info(f"[{order.id}] Step '{step_name}' already done — skipping")
    return done


# ─────────────────────────────────────────────────────────────────────────────
# MAIN TASK
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3, name='orders.process_order')
def process_order(self, order_id):
    """
    Background task — processes one order.

    Flow:
    1. Load order
    2. Safety checks
    3. Mark PROCESSING
    4. Payment step (Razorpay — skipped if already done)
    5. Inventory step (with DB locking — skipped if already done)
    6. Mark COMPLETED
    """
    from .models import Order, OrderStatus

    logger.info(f"[{order_id}] Task started (attempt {self.request.retries + 1}/4)")

    # ── Load order ────────────────────────────────────────────────────────────
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        logger.error(f"[{order_id}] Order not found — aborting")
        return

    # ── Terminal state guard ──────────────────────────────────────────────────
    from .models import OrderStatus
    if order.status in [
        OrderStatus.COMPLETED,
        OrderStatus.FAILED,
        OrderStatus.CANCELLED
    ]:
        logger.warning(f"[{order_id}] Already in terminal state — skipping")
        return

    # ── Mark PROCESSING ───────────────────────────────────────────────────────
    if order.status == OrderStatus.PENDING:
        old_status = order.status
        order.status = OrderStatus.PROCESSING
        order.save(update_fields=['status', 'updated_at'])
        log_status_transition(order_id, old_status, 'processing')

    # ── STEP 1: Payment (Razorpay) ────────────────────────────────────────────
    if not step_already_completed(order, 'payment'):
        try:
            # Calculate total in paise (1 INR = 100 paise)
            total_inr = sum(
                item['price'] * item['quantity']
                for item in order.items
            )
            amount_paise = int(total_inr * 100)

            log_step_started(order_id, 'payment', self.request.retries + 1)
            razorpay_order = create_razorpay_order(amount_paise, order_id)

            # Store razorpay order ID so the frontend can use it
            metadata = order.retry_metadata or {}
            metadata['razorpay_order_id'] = razorpay_order['id']
            metadata['amount_paise'] = amount_paise
            order.retry_metadata = metadata
            order.save(update_fields=['retry_metadata', 'updated_at'])

            # Mark payment step as "awaiting_payment"
            # The actual payment confirmation comes via webhook
            # For now we mark success (webhook flow covered in views)
            update_step_metadata(order, 'payment', 'success')
            log_step_success(order_id, 'payment', self.request.retries + 1)

        except Exception as exc:
            update_step_metadata(order, 'payment', 'failed', str(exc))
            will_retry = self.request.retries < self.max_retries
            countdown  = 2 ** self.request.retries if will_retry else None
            log_step_failed(order_id, 'payment', self.request.retries + 1,
                            exc, will_retry, countdown)

            if will_retry:
                raise self.retry(exc=exc, countdown=countdown)
            else:
                log_order_failed(order_id, str(exc))
                log_status_transition(order_id, 'processing', 'failed')
                order.status = OrderStatus.FAILED
                order.save(update_fields=['status', 'updated_at'])
                return

    # ── STEP 2: Inventory (with locking) ─────────────────────────────────────
    if not step_already_completed(order, 'inventory'):
        try:
            from .models import Reservation
            already_reserved = Reservation.objects.filter(
                order_id=order_id,
                confirmed=True
            ).exists()

            if already_reserved:
                logger.info(f"[{order_id}] Inventory already deducted via reservation — skipping")
            else:
                check_and_deduct_inventory(order_id, order.items)

            update_step_metadata(order, 'inventory', 'success')

        except Exception as exc:
            update_step_metadata(order, 'inventory', 'failed', str(exc))
            logger.warning(f"[{order_id}] Inventory step failed: {exc}")

            if self.request.retries < self.max_retries:
                raise self.retry(exc=exc, countdown=2 ** self.request.retries)
            else:
                order.status = OrderStatus.FAILED
                order.save(update_fields=['status', 'updated_at'])
                return

    # ── COMPLETED ─────────────────────────────────────────────────────────────
    order.status = OrderStatus.COMPLETED
    order.save(update_fields=['status', 'updated_at'])
    log_status_transition(order_id, 'processing', 'completed')
    log_order_completed(order_id)