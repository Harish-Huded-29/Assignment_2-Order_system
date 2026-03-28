# orders/logger.py

import logging

# Get the logger configured in settings.py
logger = logging.getLogger('orders')


def log_order_created(order_id, idempotency_key=None, items=None):
    """Called when a new order is saved to the database."""
    logger.info(
        "order_created",
        extra={
            'event':           'order_created',
            'order_id':        str(order_id),
            'idempotency_key': idempotency_key,
            'items_count':     len(items) if items else 0,
        }
    )


def log_order_duplicate(order_id, idempotency_key):
    """Called when a duplicate request is detected and blocked."""
    logger.info(
        "duplicate_request_blocked",
        extra={
            'event':           'duplicate_request_blocked',
            'order_id':        str(order_id),
            'idempotency_key': idempotency_key,
        }
    )


def log_status_transition(order_id, from_status, to_status):
    """
    Called every time an order changes state.
    This is the most important log — you can reconstruct
    the entire history of an order from these events.
    """
    logger.info(
        "order_status_changed",
        extra={
            'event':       'order_status_changed',
            'order_id':    str(order_id),
            'from_status': from_status,
            'to_status':   to_status,
        }
    )


def log_step_started(order_id, step, attempt):
    """Called when a processing step begins."""
    logger.info(
        "step_started",
        extra={
            'event':    'step_started',
            'order_id': str(order_id),
            'step':     step,
            'attempt':  attempt,
        }
    )


def log_step_success(order_id, step, attempt):
    """Called when a processing step completes successfully."""
    logger.info(
        "step_success",
        extra={
            'event':    'step_success',
            'order_id': str(order_id),
            'step':     step,
            'attempt':  attempt,
        }
    )


def log_step_failed(order_id, step, attempt, error, will_retry, countdown=None):
    """
    Called when a processing step fails.
    will_retry=True → another attempt will follow
    will_retry=False → all retries exhausted, order will be FAILED
    """
    logger.warning(
        "step_failed",
        extra={
            'event':      'step_failed',
            'order_id':   str(order_id),
            'step':       step,
            'attempt':    attempt,
            'error':      str(error),
            'will_retry': will_retry,
            'countdown':  countdown,
        }
    )


def log_order_completed(order_id):
    """Called when an order successfully completes all steps."""
    logger.info(
        "order_completed",
        extra={
            'event':    'order_completed',
            'order_id': str(order_id),
        }
    )


def log_order_failed(order_id, reason):
    """Called when an order exhausts all retries and permanently fails."""
    logger.error(
        "order_failed",
        extra={
            'event':    'order_failed',
            'order_id': str(order_id),
            'reason':   reason,
        }
    )


def log_order_cancelled(order_id, cancelled_from_status):
    """Called when a user cancels an order."""
    logger.info(
        "order_cancelled",
        extra={
            'event':                 'order_cancelled',
            'order_id':              str(order_id),
            'cancelled_from_status': cancelled_from_status,
        }
    )


def log_celery_task_revoked(order_id, task_id):
    """Called when a Celery task is revoked during cancellation."""
    logger.info(
        "celery_task_revoked",
        extra={
            'event':    'celery_task_revoked',
            'order_id': str(order_id),
            'task_id':  task_id,
        }
    )


def log_payment_verified(order_id, razorpay_payment_id):
    """Called when Razorpay payment signature is verified successfully."""
    logger.info(
        "payment_verified",
        extra={
            'event':                'payment_verified',
            'order_id':             str(order_id),
            'razorpay_payment_id':  razorpay_payment_id,
        }
    )


def log_payment_verification_failed(order_id):
    """Called when Razorpay signature verification fails — possible fraud attempt."""
    logger.error(
        "payment_verification_failed",
        extra={
            'event':    'payment_verification_failed',
            'order_id': str(order_id),
        }
    )


def log_inventory_deducted(order_id, item_name, quantity_deducted, quantity_remaining):
    """Called when inventory is successfully deducted for an item."""
    logger.info(
        "inventory_deducted",
        extra={
            'event':               'inventory_deducted',
            'order_id':            str(order_id),
            'item_name':           item_name,
            'quantity_deducted':   quantity_deducted,
            'quantity_remaining':  quantity_remaining,
        }
    )


def log_inventory_insufficient(order_id, item_name, needed, available):
    """Called when there is not enough stock to fulfil an order item."""
    logger.warning(
        "inventory_insufficient",
        extra={
            'event':     'inventory_insufficient',
            'order_id':  str(order_id),
            'item_name': item_name,
            'needed':    needed,
            'available': available,
        }
    )