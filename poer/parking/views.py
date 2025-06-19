from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta
from django.http import HttpResponse, Http404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import Group
from django.contrib.auth.views import LoginView
from .models import ParkingSpot, Car, ParkingLog, Payment
from .reports import ReportGenerator

class CustomLoginView(LoginView):
    template_name = 'parking/login.html'
    redirect_authenticated_user = True

def is_admin(user):
    return user.groups.filter(name='Administrator').exists()

def is_receptionist(user):
    return user.groups.filter(name='Receptionist').exists()

def is_client(user):
    return user.groups.filter(name='Client').exists()

@login_required
def home(request):
    spots = ParkingSpot.objects.all()
    total_spots = spots.count()
    available_spots = sum(1 for spot in spots if spot.is_available)
    occupied_spots = total_spots - available_spots
    
    # Определяем доступные действия в зависимости от роли
    can_manage = is_admin(request.user)
    can_control_barrier = is_admin(request.user) or is_receptionist(request.user)
    can_reserve = is_client(request.user)
    can_view_reports = is_admin(request.user)
    
    context = {
        'spots': spots,
        'total_spots': total_spots,
        'available_spots': available_spots,
        'occupied_spots': occupied_spots,
        'can_manage': can_manage,
        'can_control_barrier': can_control_barrier,
        'can_reserve': can_reserve,
        'can_view_reports': can_view_reports,
    }
    return render(request, 'parking/home.html', context)

@login_required
@user_passes_test(is_client)
def reserve(request):
    if request.method == 'POST':
        license_plate = request.POST.get('license_plate')
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')
        spot_id = request.POST.get('spot')
        
        try:
            spot = ParkingSpot.objects.get(id=spot_id)
            car, created = Car.objects.get_or_create(license_plate=license_plate)
            
            if spot.is_available_for_reservation(start_time, end_time):
                spot.reserve(car, start_time, end_time)
                messages.success(request, 'Место успешно забронировано!')
                return redirect('parking:home')
            else:
                messages.error(request, 'Выбранное место недоступно для бронирования в указанное время')
        except ParkingSpot.DoesNotExist:
            messages.error(request, 'Выбранное место не существует')
        except Exception as e:
            messages.error(request, f'Ошибка при бронировании: {str(e)}')
    
    # Получаем список доступных мест
    available_spots = ParkingSpot.objects.filter(is_available=True)
    return render(request, 'parking/reserve.html', {'spots': available_spots})

@login_required
@user_passes_test(is_client)
def pay(request):
    if request.method == 'POST':
        license_plate = request.POST.get('license_plate')
        hours = int(request.POST.get('hours', 1))
        
        try:
            car = Car.objects.get(license_plate=license_plate)
            # Получаем текущий активный лог парковки
            parking_log = ParkingLog.objects.filter(
                car=car,
                exit_time__isnull=True
            ).first()
            
            if not parking_log:
                messages.error(request, 'Нет активной парковки для этого автомобиля')
                return redirect('parking:pay')
            
            # Создаем платеж
            payment = Payment.objects.create(
                parking_log=parking_log,
                amount=hours * 100,  # 100 рублей в час
                status='completed',
                payment_time=timezone.now()
            )
            
            # Обновляем время выезда
            parking_log.exit_time = timezone.now() + timedelta(hours=hours)
            parking_log.save()
            
            # Освобождаем место
            spot = parking_log.spot
            spot.is_occupied = False
            spot.is_reserved = False
            spot.reservation_start = None
            spot.reservation_end = None
            spot.save()
            
            messages.success(request, 'Оплата успешно произведена!')
            return redirect('parking:home')
            
        except Car.DoesNotExist:
            messages.error(request, 'Автомобиль с таким номером не найден')
        except Exception as e:
            messages.error(request, f'Ошибка при оплате: {str(e)}')
        return redirect('parking:pay')
    
    return render(request, 'parking/pay.html')

@login_required
@user_passes_test(is_admin)
def daily_report(request):
    """Представление для генерации ежедневного отчета"""
    date_str = request.GET.get('date')
    if date_str:
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return HttpResponse('Invalid date format. Use YYYY-MM-DD', status=400)
    else:
        date = timezone.now().date()

    report_generator = ReportGenerator()
    excel_content = report_generator.generate_daily_report_excel(date)
    
    response = HttpResponse(excel_content, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="daily_report_{date}.xlsx"'
    return response

@login_required
@user_passes_test(is_admin)
def monthly_report(request):
    """Представление для генерации месячного отчета"""
    try:
        year = int(request.GET.get('year', timezone.now().year))
        month = int(request.GET.get('month', timezone.now().month))
        
        if not (1 <= month <= 12):
            return HttpResponse('Month must be between 1 and 12', status=400)
            
        report_generator = ReportGenerator()
        excel_content = report_generator.generate_monthly_report_excel(year, month)
        
        response = HttpResponse(excel_content, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="monthly_report_{year}_{month:02d}.xlsx"'
        return response
    except ValueError as e:
        return HttpResponse(str(e), status=400)

@login_required
@user_passes_test(lambda u: is_admin(u) or is_receptionist(u))
def control_barrier(request):
    """Управление шлагбаумом"""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'open':
            # Логика открытия шлагбаума
            messages.success(request, 'Шлагбаум открыт')
        elif action == 'close':
            # Логика закрытия шлагбаума
            messages.success(request, 'Шлагбаум закрыт')
        return redirect('parking:home')
    
    return render(request, 'parking/control_barrier.html')
