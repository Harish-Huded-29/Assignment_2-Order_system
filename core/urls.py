# config/urls.py

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # Django's built-in admin panel
    path('admin/', admin.site.urls),

    # All routes starting with /api/ go to the orders app
    # We'll add actual routes there on Day 2
    path('api/', include('orders.urls')),
]