from rest_framework import serializers
from .models import ParkingSpot, Car, ParkingLog, Payment
from django.utils import timezone

class ParkingSpotSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParkingSpot
        fields = ['id', 'number', 'is_available', 'is_reserved', 
                 'reservation_start', 'reservation_end', 'reservation_timeout']

    def validate(self, data):
        if data.get('is_reserved'):
            start_time = data.get('reservation_start')
            end_time = data.get('reservation_end')
            
            if not start_time or not end_time:
                raise serializers.ValidationError(
                    "Для резервации необходимо указать время начала и окончания"
                )
            
            if start_time >= end_time:
                raise serializers.ValidationError(
                    "Время начала должно быть раньше времени окончания"
                )
            
            if start_time < timezone.now():
                raise serializers.ValidationError(
                    "Нельзя резервировать место в прошлом"
                )
        
        return data

class CarSerializer(serializers.ModelSerializer):
    class Meta:
        model = Car
        fields = ['id', 'number', 'owner', 'phone']

class ParkingLogSerializer(serializers.ModelSerializer):
    duration = serializers.SerializerMethodField()
    
    class Meta:
        model = ParkingLog
        fields = ['id', 'car', 'spot', 'entry_time', 'exit_time',
                 'is_reservation', 'reservation_start', 'reservation_end',
                 'duration']

    def get_duration(self, obj):
        return obj.calculate_duration()

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'parking_log', 'amount', 'status', 'payment_time'] 