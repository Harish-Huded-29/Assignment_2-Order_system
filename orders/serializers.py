# orders/serializers.py

from decimal import Decimal
from rest_framework import serializers
from .models import Order


class OrderItemSerializer(serializers.Serializer):
    """
    Validates each item in the order.
    We use FloatField for price instead of DecimalField —
    this way the value stays JSON-serializable when stored in JSONField.
    """
    name     = serializers.CharField(max_length=100)
    quantity = serializers.IntegerField(min_value=1)
    price    = serializers.FloatField(min_value=0)  # Float = JSON safe ✅


class OrderSerializer(serializers.ModelSerializer):

    items = OrderItemSerializer(many=True)

    class Meta:
        model  = Order
        fields = [
            'id',
            'items',
            'status',
            'retry_metadata',
            'celery_task_id',
            'idempotency_key',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'status',
            'retry_metadata',
            'celery_task_id',
            'created_at',
            'updated_at',
        ]

    def create(self, validated_data):
        """
        Custom create method.
        Why? Because OrderItemSerializer returns a list of dicts with
        Python objects inside. We need to make sure items is a plain
        JSON-safe list before saving to the database.
        """
        # items is already a list of dicts from the serializer
        # but we explicitly convert to be safe
        items = validated_data.pop('items')

        # Convert any non-JSON-safe types just in case
        clean_items = []
        for item in items:
            clean_items.append({
                'name':     item['name'],
                'quantity': int(item['quantity']),
                'price':    float(item['price']),  # Decimal → float ✅
            })

        # Now create the order with clean data
        order = Order.objects.create(
            items=clean_items,
            **validated_data
        )
        return order


class OrderListSerializer(serializers.ModelSerializer):
    """
    Lighter serializer for list endpoint — only key fields.
    """
    class Meta:
        model  = Order
        fields = ['id', 'status', 'created_at', 'updated_at']