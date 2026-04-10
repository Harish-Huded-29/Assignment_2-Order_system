# orders/models.py

import uuid
from django.db import models


class OrderStatus(models.TextChoices):
    """
    Think of this as a list of allowed values for the 'status' field.
    An order can ONLY ever be in one of these 5 states.
    This is called a 'state machine' — you'll hear this term a lot.

    Format: CONSTANT = 'db_value', 'Human readable label'
    """
    PENDING    = 'pending',    'Pending'     # Just created, not yet sent to worker
    PROCESSING = 'processing', 'Processing'  # Worker is actively working on it
    COMPLETED  = 'completed',  'Completed'   # All steps passed successfully
    FAILED     = 'failed',     'Failed'      # All retries exhausted, gave up
    CANCELLED  = 'cancelled',  'Cancelled'   # User cancelled it


class Order(models.Model):
    """
    This class = one table in your PostgreSQL database.
    Each attribute = one column in that table.
    Each instance of Order = one row.
    """

    # ── Primary Key ──────────────────────────────────────────────────────────
    # UUID = a random unique ID like "550e8400-e29b-41d4-a716-446655440000"
    # Better than 1, 2, 3... because:
    #   - Doesn't reveal how many orders you have
    #   - Safe to generate without hitting the DB first
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,   # Auto-generate a new UUID for every order
        editable=False        # Can't be changed after creation
    )

    # ── Order Contents ───────────────────────────────────────────────────────
    # JSONField stores any JSON structure — no fixed columns needed
    # Example value:
    # [
    #   {"name": "burger", "quantity": 2, "price": 5.99},
    #   {"name": "fries",  "quantity": 1, "price": 2.49}
    # ]
    items = models.JSONField()

    # ── Status ───────────────────────────────────────────────────────────────
    # Uses the TextChoices above — Django enforces only valid values
    # Every order starts as PENDING
    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
    )

    # ── Idempotency Key ──────────────────────────────────────────────────────
    # The client sends a unique key with each request (like a UUID)
    # If the same key comes in again → return the existing order, don't create new
    # unique=True → PostgreSQL enforces no two orders have the same key
    # null=True  → allows orders created without a key (backward compatible)
    idempotency_key = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True
    )

    # ── Retry Metadata ───────────────────────────────────────────────────────
    # Tracks how many times each processing step has been retried
    # Example value:
    # {
    #   "payment":   {"attempts": 2, "last_error": "timeout"},
    #   "inventory": {"attempts": 0, "last_error": null}
    # }
    # default=dict means it starts as {} (empty dict) for every new order
    retry_metadata = models.JSONField(default=dict)

    # ── Celery Task ID ───────────────────────────────────────────────────────
    # When we send work to Celery (Day 3), Celery gives back a task ID
    # We store it here so we can CANCEL the task later (Day 6)
    celery_task_id = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    # ── Timestamps ───────────────────────────────────────────────────────────
    # auto_now_add=True → set ONCE when the row is first created, never changes
    # auto_now=True     → updated EVERY time you call order.save()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'orders'          # Exact table name in PostgreSQL
        ordering = ['-created_at']   # Newest orders first in queries

    def __str__(self):
        # This is what shows up in Django Admin and print() calls
        return f"Order {self.id} [{self.status}]"
    

# Add this to the bottom of orders/models.py

class Inventory(models.Model):
    """
    Tracks available stock for each item.

    WHY a separate table and not inside Order?
    Because inventory is SHARED across all orders.
    "How many burgers do we have?" is a global question,
    not per-order. It needs to be one row that all
    concurrent workers read and update safely.

    Example row:
      item_name = "burger"
      quantity  = 5
    """

    item_name = models.CharField(max_length=100, unique=True)
    quantity  = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'inventory'

    def __str__(self):
        return f"{self.item_name}: {self.quantity}"
    

# ─── ADD THIS ENTIRE BLOCK AT THE BOTTOM OF models.py ───────────────────────

class Reservation(models.Model):
    """
    A temporary "hold" on inventory.

    When a user clicks "Add to Cart" we immediately deduct from inventory
    and create a Reservation row. This prevents two users from buying
    the same last item.

    If the user pays → Reservation stays, order is processed.
    If the user cancels Razorpay → we restore the inventory and delete this row.
    Reservations expire after 10 minutes (handled in the view).
    """

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item_name  = models.CharField(max_length=100)
    quantity   = models.IntegerField()
    session_key = models.CharField(max_length=255)   # ties reservation to a browser tab
    order      = models.ForeignKey(
        'Order', null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed  = models.BooleanField(default=False)  # True after payment succeeds

    class Meta:
        db_table = 'reservations'

    def __str__(self):
        return f"Reservation {self.id}: {self.quantity}x {self.item_name}"