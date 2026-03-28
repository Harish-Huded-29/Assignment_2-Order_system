# orders/views.py

import logging
from rest_framework     import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts   import get_object_or_404
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models      import Order
from .serializers import OrderSerializer, OrderListSerializer

import logging
logger = logging.getLogger('orders')
from .logger import (
    log_order_created, log_order_duplicate, log_status_transition,
    log_order_cancelled, log_celery_task_revoked,
    log_payment_verified, log_payment_verification_failed,
)


class OrderCreateView(APIView):
    """
    POST /api/orders/
    Creates a new order.

    APIView = Django REST Framework's base class for views.
    We define a 'post' method — DRF calls it when a POST request arrives.
    """

    def post(self, request):
        # ── Step 1: Read idempotency key from header ──────────────────────────
        # The client sends a unique key like: Idempotency-Key: some-uuid
        # HTTP headers in Django have 'HTTP_' prefix and are uppercased
        idempotency_key = request.headers.get('Idempotency-Key')

        # ── Step 2: Check for duplicate request ───────────────────────────────
        # If we've seen this key before, return the existing order
        # This is Phase 4 (Idempotency) — built in from day one!
        if idempotency_key:
            existing = Order.objects.filter(
                idempotency_key=idempotency_key
            ).first()
            if existing:
                log_order_duplicate(existing.id, idempotency_key)
                serializer = OrderSerializer(existing)
                # 200 OK (not 201) — nothing new was created
                return Response(serializer.data, status=status.HTTP_200_OK)

        # ── Step 3: Validate the incoming JSON ────────────────────────────────
        # Pass request.data (the parsed JSON body) into our serializer
        # The serializer checks: are all required fields present? correct types?
        serializer = OrderSerializer(data=request.data)

        if not serializer.is_valid():
            # Validation failed — tell the client exactly what's wrong
            # Example: {"items": [{"price": ["A valid number is required."]}]}
            logger.warning(f"Order creation failed validation: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # ── Step 4: Save to database ──────────────────────────────────────────
        # Pass idempotency_key so it gets stored with the order
        order = serializer.save(idempotency_key=idempotency_key)
        log_order_created(order.id, idempotency_key, order.items)
        # ── Queue the background task ─────────────────────────────────────────
        # .delay() sends the task to Redis — Celery worker picks it up
        # We pass order.id as a string (UUIDs need str() conversion)
        # The view does NOT wait for this — it returns immediately after
        from .tasks import process_order
        task = process_order.delay(str(order.id))

        # Store the Celery task ID so we can cancel it later (Day 6)
        order.celery_task_id = task.id
        order.save(update_fields=['celery_task_id'])

        # ── Step 5: Return the created order ─────────────────────────────────
        # 201 CREATED = the standard HTTP code for "resource was created"
        return Response(
            OrderSerializer(order).data,
            status=status.HTTP_201_CREATED
        )


class OrderDetailView(APIView):
    """
    GET /api/orders/<id>/
    Returns a single order by its UUID.
    """

    def get(self, request, order_id):
        # get_object_or_404:
        #   - If found → returns the Order object
        #   - If not found → automatically returns 404 response
        # Much cleaner than try/except Order.DoesNotExist
        order = get_object_or_404(Order, id=order_id)

        serializer = OrderSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)


class OrderListView(APIView):
    """
    GET /api/orders/
    Returns a list of orders.
    Supports filtering by status via query parameter:
      /api/orders/?status=pending
      /api/orders/?status=completed
    """

    def get(self, request):
        # Start with ALL orders (newest first — set in model Meta)
        queryset = Order.objects.all()

        # ── Optional filter by status ──────────────────────────────────────
        # request.query_params is a dict of URL params like ?status=pending
        status_filter = request.query_params.get('status')

        if status_filter:
            # Validate the status value before filtering
            # Prevents random values like ?status=banana
            valid_statuses = [s.value for s in Order.OrderStatus
                              ] if hasattr(Order, 'OrderStatus') else [
                'pending', 'processing', 'completed', 'failed', 'cancelled'
            ]
            if status_filter not in valid_statuses:
                return Response(
                    {"error": f"Invalid status. Choose from: {valid_statuses}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            queryset = queryset.filter(status=status_filter)

        # many=True tells the serializer it's a list, not a single object
        serializer = OrderListSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

    # Add at the top of views.py with other imports
import razorpay
from django.conf import settings


@method_decorator(csrf_exempt, name='dispatch')
class RazorpayOrderCreateView(APIView):
    """
    POST /api/orders/razorpay/create/

    Creates both our Order and a Razorpay order object.
    The frontend uses the Razorpay order ID to show the payment popup.

    Flow:
    Client → POST here → we create DB order + Razorpay order
           → return both IDs to frontend
           → frontend shows Razorpay popup
           → customer pays
           → frontend calls /api/orders/razorpay/verify/
    """

    def post(self, request):
        idempotency_key = request.headers.get('Idempotency-Key')

        # Check duplicate
        if idempotency_key:
            existing = Order.objects.filter(
                idempotency_key=idempotency_key
            ).first()
            if existing:
                return Response(
                    OrderSerializer(existing).data,
                    status=status.HTTP_200_OK
                )

        # Validate and create order
        serializer = OrderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        order = serializer.save(idempotency_key=idempotency_key)

        # Create Razorpay order
        total_inr = sum(
            item['price'] * item['quantity']
            for item in order.items
        )
        amount_paise = int(total_inr * 100)

        try:
            client = razorpay.Client(
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
            )
            rzp_order = client.order.create({
                'amount':   amount_paise,
                'currency': 'INR',
                'receipt':  str(order.id)[:40],
            })
        except Exception as e:
            # Delete the order we just created since payment setup failed
            order.delete()
            logger.error(f"Razorpay error: {e}")
            return Response(
                {'error': f'Payment gateway error: {str(e)}'},
                status=status.HTTP_502_BAD_GATEWAY
            )

        # Store Razorpay order ID in our order's metadata
        order.retry_metadata = {
            'razorpay_order_id': rzp_order['id'],
            'amount_paise': amount_paise,
        }
        order.save(update_fields=['retry_metadata', 'updated_at'])

        log_order_created(order.id, idempotency_key, order.items)

        return Response({
            'order': OrderSerializer(order).data,
            'razorpay_order_id': rzp_order['id'],
            'razorpay_key_id':   settings.RAZORPAY_KEY_ID,
            'amount_paise':      amount_paise,
        }, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name='dispatch')
class RazorpayVerifyView(APIView):
    """
    POST /api/orders/razorpay/verify/

    Called by the frontend AFTER the customer completes payment.
    Razorpay sends back 3 values — we verify the signature,
    then queue the background processing task.

    WHY verify? To prove the payment really happened.
    Anyone could POST fake values — the signature check
    uses our secret key to confirm it's genuine.
    """

    def post(self, request):
        order_id            = request.data.get('order_id')
        razorpay_order_id   = request.data.get('razorpay_order_id')
        razorpay_payment_id = request.data.get('razorpay_payment_id')
        razorpay_signature  = request.data.get('razorpay_signature')

        if not all([order_id, razorpay_order_id,
                    razorpay_payment_id, razorpay_signature]):
            return Response(
                {'error': 'Missing payment verification fields'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify signature
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
        try:
            client.utility.verify_payment_signature({
                'razorpay_order_id':   razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature':  razorpay_signature,
            })
        except Exception:
            return Response(
                {'error': 'Payment verification failed — signature mismatch'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Load our order
        order = get_object_or_404(Order, id=order_id)

        # Store payment ID for records
        metadata = order.retry_metadata or {}
        metadata['razorpay_payment_id'] = razorpay_payment_id
        metadata['payment'] = {'status': 'success', 'attempts': 1, 'last_error': None}
        order.retry_metadata = metadata
        order.save(update_fields=['retry_metadata', 'updated_at'])

        # Now queue background task for inventory check
        from .tasks import process_order
        task = process_order.delay(str(order.id))
        order.celery_task_id = task.id
        order.save(update_fields=['celery_task_id'])

        log_payment_verified(order.id, razorpay_payment_id)

        return Response({
            'message': 'Payment verified. Order is being processed.',
            'order_id': str(order.id),
        }, status=status.HTTP_200_OK)
    
from django.shortcuts import render
from .models import Inventory


class InventoryListView(APIView):
    """GET /api/inventory/ — returns current stock levels"""
    def get(self, request):
        items = Inventory.objects.all().order_by('item_name')
        data  = [{'item_name': i.item_name, 'quantity': i.quantity} for i in items]
        return Response(data)


class OrderCancelView(APIView):
    """POST /api/orders/<id>/cancel/"""
    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id)

        if order.status in ['completed', 'failed', 'cancelled']:
            return Response(
                {'error': f'Cannot cancel — order is already {order.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Revoke Celery task if running
        if order.celery_task_id:
            from celery.app.control import Control
            from core.celery import app as celery_app
            celery_app.control.revoke(order.celery_task_id, terminate=True)
            log_celery_task_revoked(order.id, order.celery_task_id)

        order.status = 'cancelled'
        order.save(update_fields=['status', 'updated_at'])
        old_status = order.status
        order.status = 'cancelled'
        order.save(update_fields=['status', 'updated_at'])
        log_order_cancelled(order.id, old_status)
        log_status_transition(order.id, old_status, 'cancelled')

        return Response({'message': 'Order cancelled successfully'})


def ui_view(request):
    """Serves the HTML UI — also ensures CSRF cookie is set"""
    get_token(request)  # Forces Django to set the csrftoken cookie
    return render(request, 'orders/index.html')