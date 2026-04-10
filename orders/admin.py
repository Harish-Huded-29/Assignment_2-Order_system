# orders/admin.py

from django.contrib import admin
from .models import Order, Inventory

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    # Columns shown in the list view
    list_display = ['id', 'status', 'created_at', 'updated_at']
    # Filter sidebar on the right
    list_filter = ['status']
    # These fields can't be edited (auto-generated)
    readonly_fields = ['id', 'created_at', 'updated_at']

@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ['item_name', 'quantity', 'updated_at']