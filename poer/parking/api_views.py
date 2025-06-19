from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.http import HttpResponse
from datetime import datetime
from .models import ParkingSpot, Car, ParkingLog, Payment
from .serializers import (
    ParkingSpotSerializer, CarSerializer,
    ParkingLogSerializer, PaymentSerializer
)
from .equipment import ParkingSystem
from .reports import ReportGenerator
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class ParkingSpotViewSet(viewsets.ModelViewSet):
    queryset = ParkingSpot.objects.all()
    serializer_class = ParkingSpotSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    @action(detail=False, methods=['get'])
    def available(self, request):
        """Получение списка доступных мест"""
        spots = self.queryset.filter(is_available=True)
        serializer = self.get_serializer(spots, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def reserve(self, request, pk=None):
        """Резервация места на указанный период"""
        spot = self.get_object()
        start_time = request.data.get('start_time')
        end_time = request.data.get('end_time')

        if not start_time or not end_time:
            return Response(
                {'error': 'Необходимо указать время начала и окончания резервации'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            start_time = timezone.datetime.fromisoformat(start_time)
            end_time = timezone.datetime.fromisoformat(end_time)
        except ValueError:
            return Response(
                {'error': 'Неверный формат времени'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if spot.reserve(start_time, end_time):
            # Создаем запись о резервации
            ParkingLog.objects.create(
                car=request.user.car,
                spot=spot,
                entry_time=start_time,
                is_reservation=True,
                reservation_start=start_time,
                reservation_end=end_time
            )
            return Response(self.get_serializer(spot).data)
        else:
            return Response(
                {'error': 'Место недоступно для резервации в указанный период'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def cancel_reservation(self, request, pk=None):
        """Отмена резервации"""
        spot = self.get_object()
        if not spot.is_reserved:
            return Response(
                {'error': 'Место не зарезервировано'},
                status=status.HTTP_400_BAD_REQUEST
            )

        spot.cancel_reservation()
        return Response(self.get_serializer(spot).data)

    @action(detail=False, methods=['get'])
    def check_timeouts(self, request):
        """Проверка и отмена просроченных резерваций"""
        spots = self.queryset.filter(is_reserved=True)
        cancelled = []
        
        for spot in spots:
            if spot.check_reservation_timeout():
                cancelled.append(spot)
        
        serializer = self.get_serializer(cancelled, many=True)
        return Response({
            'cancelled_count': len(cancelled),
            'cancelled_spots': serializer.data
        })

class CarViewSet(viewsets.ModelViewSet):
    queryset = Car.objects.all()
    serializer_class = CarSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = Car.objects.all()
        license_plate = self.request.query_params.get('license_plate', None)
        if license_plate:
            queryset = queryset.filter(license_plate__icontains=license_plate)
        return queryset

class ParkingLogViewSet(viewsets.ModelViewSet):
    queryset = ParkingLog.objects.all()
    serializer_class = ParkingLogSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    @action(detail=False, methods=['get'])
    def active_reservations(self, request):
        """Получение активных резерваций"""
        now = timezone.now()
        reservations = self.queryset.filter(
            is_reservation=True,
            reservation_start__lte=now,
            reservation_end__gte=now
        )
        serializer = self.get_serializer(reservations, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def future_reservations(self, request):
        """Получение будущих резерваций"""
        now = timezone.now()
        reservations = self.queryset.filter(
            is_reservation=True,
            reservation_start__gt=now
        )
        serializer = self.get_serializer(reservations, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def exit(self, request, pk=None):
        log = self.get_object()
        if log.exit_time:
            return Response(
                {'error': 'Автомобиль уже выехал'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        log.exit_time = timezone.now()
        log.spot.is_occupied = False
        log.spot.save()
        log.save()
        return Response(self.get_serializer(log).data)

class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        payment = self.get_object()
        if payment.status == 'completed':
            return Response(
                {'error': 'Платеж уже завершен'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        payment.status = 'completed'
        payment.payment_time = timezone.now()
        payment.save()
        return Response(self.get_serializer(payment).data)

    @action(detail=True, methods=['get'])
    def receipt(self, request, pk=None):
        """Получить PDF-чек об оплате"""
        payment = self.get_object()
        report_generator = ReportGenerator()
        pdf_content = report_generator.generate_receipt_pdf(payment)
        
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="receipt_{payment.id}.pdf"'
        return response

    @action(detail=False, methods=['get'])
    def daily_report(self, request):
        """Получить ежедневный отчет"""
        try:
            date_str = request.query_params.get('date')
            if date_str:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
            else:
                date = None

            report_generator = ReportGenerator()
            excel_content = report_generator.generate_daily_report_excel(date)
            
            response = HttpResponse(excel_content, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="daily_report_{date or datetime.now().date()}.xlsx"'
            return response
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def monthly_report(self, request):
        """Получить месячный отчет"""
        try:
            year = int(request.query_params.get('year', datetime.now().year))
            month = int(request.query_params.get('month', datetime.now().month))

            if not (1 <= month <= 12):
                raise ValueError('Month must be between 1 and 12')

            report_generator = ReportGenerator()
            excel_content = report_generator.generate_monthly_report_excel(year, month)
            
            response = HttpResponse(excel_content, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="monthly_report_{year}_{month:02d}.xlsx"'
            return response
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class EquipmentViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.parking_system = ParkingSystem(
            camera_url=settings.CAMERA_URL,
            barrier_url=settings.BARRIER_URL,
            camera_credentials=settings.CAMERA_CREDENTIALS,
            barrier_api_key=settings.BARRIER_API_KEY,
            alpr_path=settings.ALPR_PATH
        )

    @action(detail=False, methods=['post'])
    def process_entry(self, request):
        """Обработка въезда автомобиля"""
        try:
            success, message = self.parking_system.process_vehicle_entry()
            if success:
                return Response({'status': 'success', 'message': message})
            else:
                return Response(
                    {'status': 'error', 'message': message},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            logger.error(f"Ошибка при обработке въезда: {str(e)}")
            return Response(
                {'status': 'error', 'message': 'Внутренняя ошибка сервера'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def process_exit(self, request):
        """Обработка выезда автомобиля"""
        try:
            success, message = self.parking_system.process_vehicle_exit()
            if success:
                return Response({'status': 'success', 'message': message})
            else:
                return Response(
                    {'status': 'error', 'message': message},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            logger.error(f"Ошибка при обработке выезда: {str(e)}")
            return Response(
                {'status': 'error', 'message': 'Внутренняя ошибка сервера'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def barrier_status(self, request):
        """Получение статуса шлагбаума"""
        try:
            status = self.parking_system.barrier.get_status()
            if status is not None:
                return Response({'status': 'success', 'data': status})
            else:
                return Response(
                    {'status': 'error', 'message': 'Не удалось получить статус шлагбаума'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        except Exception as e:
            logger.error(f"Ошибка при получении статуса шлагбаума: {str(e)}")
            return Response(
                {'status': 'error', 'message': 'Внутренняя ошибка сервера'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            ) 