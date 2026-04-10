# orders/urls.py

from django.urls import path
from .views import (
    OrderCreateView, OrderDetailView, OrderListView,
    RazorpayOrderCreateView, RazorpayVerifyView,
    InventoryListView, OrderCancelView, ui_view,
    ReserveInventoryView, ReleaseReservationView, inventory_sse,
)

urlpatterns = [
    path('',                                  ui_view,                           name='ui'),
    path('orders/',                           OrderCreateView.as_view(),         name='order-create'),
    path('orders/list/',                      OrderListView.as_view(),           name='order-list'),
    path('orders/razorpay/create/',           RazorpayOrderCreateView.as_view(), name='razorpay-create'),
    path('orders/razorpay/verify/',           RazorpayVerifyView.as_view(),      name='razorpay-verify'),
    path('orders/<uuid:order_id>/',           OrderDetailView.as_view(),         name='order-detail'),
    path('orders/<uuid:order_id>/cancel/',    OrderCancelView.as_view(),         name='order-cancel'),
    path('inventory/',                        InventoryListView.as_view(),        name='inventory'),
    path('inventory/reserve/',                ReserveInventoryView.as_view(),     name='inventory-reserve'),
    path('inventory/release/',                ReleaseReservationView.as_view(),   name='inventory-release'),
    path('inventory/stream/',                 inventory_sse,                      name='inventory-sse'),
]