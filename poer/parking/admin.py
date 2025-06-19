from django.contrib import admin
from .models import ParkingSpot, Car, ParkingLog, Payment

@admin.register(ParkingSpot)
class ParkingSpotAdmin(admin.ModelAdmin):
    list_display = ('number', 'is_occupied', 'is_reserved')
    list_filter = ('is_occupied', 'is_reserved')
    search_fields = ('number',)
    ordering = ('number',)

@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
    list_display = ('license_plate', 'created_at')
    search_fields = ('license_plate',)
    ordering = ('license_plate',)

@admin.register(ParkingLog)
class ParkingLogAdmin(admin.ModelAdmin):
    list_display = ('car', 'spot', 'entry_time', 'exit_time')
    list_filter = ('entry_time', 'exit_time')
    search_fields = ('car__license_plate', 'spot__number')
    raw_id_fields = ('car', 'spot')
    date_hierarchy = 'entry_time'

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('parking_log', 'amount', 'status', 'payment_time')
    list_filter = ('status', 'payment_time')
    search_fields = ('parking_log__car__license_plate',)
    raw_id_fields = ('parking_log',)
    date_hierarchy = 'payment_time'
