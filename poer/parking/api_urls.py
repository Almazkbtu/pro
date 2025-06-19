from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import (
    ParkingSpotViewSet, CarViewSet,
    ParkingLogViewSet, PaymentViewSet,
    EquipmentViewSet
)

router = DefaultRouter()
router.register(r'spots', ParkingSpotViewSet)
router.register(r'cars', CarViewSet)
router.register(r'logs', ParkingLogViewSet)
router.register(r'payments', PaymentViewSet)
router.register(r'equipment', EquipmentViewSet, basename='equipment')

urlpatterns = [
    path('', include(router.urls)),
] 