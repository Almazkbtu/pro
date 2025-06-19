from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_migrate
from django.dispatch import receiver

class ParkingSpot(models.Model):
    """Модель парковочного места"""
    number = models.CharField(max_length=10, unique=True, verbose_name="Номер места")
    is_occupied = models.BooleanField(default=False, verbose_name="Занято")
    is_reserved = models.BooleanField(default=False, verbose_name="Зарезервировано")
    reservation_start = models.DateTimeField(null=True, blank=True, verbose_name="Начало резервации")
    reservation_end = models.DateTimeField(null=True, blank=True, verbose_name="Конец резервации")
    reservation_timeout = models.IntegerField(default=15, verbose_name="Таймаут резервации в минутах")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Парковочное место"
        verbose_name_plural = "Парковочные места"
        ordering = ['number']

    def __str__(self):
        return f"Место {self.number}"

    @property
    def is_available(self):
        """Проверка доступности места"""
        return not (self.is_occupied or self.is_reserved)

    @property
    def current_car(self):
        """Получение текущего автомобиля на месте"""
        try:
            return self.parkinglog_set.filter(exit_time__isnull=True).first().car
        except:
            return None

    def is_available_for_reservation(self, start_time, end_time):
        """Проверка доступности места для резервации в указанный период"""
        if not self.is_available:
            return False

        # Проверяем пересечение с существующими резервациями
        overlapping_reservations = ParkingLog.objects.filter(
            spot=self,
            exit_time__isnull=True
        ).filter(
            models.Q(entry_time__lte=end_time) & 
            models.Q(entry_time__gte=start_time)
        )
        
        return not overlapping_reservations.exists()

    def reserve(self, car, start_time, end_time):
        """Резервация места на указанный период"""
        if not self.is_available_for_reservation(start_time, end_time):
            return False

        # Создаем запись в логе
        ParkingLog.objects.create(
            car=car,
            spot=self,
            entry_time=start_time,
            is_reservation=True,
            reservation_start=start_time,
            reservation_end=end_time
        )

        self.is_reserved = True
        self.reservation_start = start_time
        self.reservation_end = end_time
        self.save()
        return True

    def cancel_reservation(self):
        """Отмена резервации"""
        self.is_reserved = False
        self.reservation_start = None
        self.reservation_end = None
        self.save()

    def check_reservation_timeout(self):
        """Проверка и отмена резервации по таймауту"""
        if self.is_reserved and self.reservation_start:
            timeout_time = self.reservation_start + timedelta(minutes=self.reservation_timeout)
            if timezone.now() > timeout_time:
                self.cancel_reservation()
                return True
        return False

class Car(models.Model):
    """Модель автомобиля"""
    license_plate = models.CharField(max_length=20, unique=True, verbose_name="Номер автомобиля")
    owner = models.CharField(max_length=100, verbose_name="Владелец", null=True, blank=True)
    phone = models.CharField(max_length=20, verbose_name="Телефон", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Автомобиль"
        verbose_name_plural = "Автомобили"
        ordering = ['license_plate']

    def __str__(self):
        return f"{self.license_plate} ({self.owner or 'Неизвестный владелец'})"

class ParkingLog(models.Model):
    """Модель лога въезда/выезда"""
    car = models.ForeignKey(Car, on_delete=models.CASCADE, verbose_name="Автомобиль")
    spot = models.ForeignKey(ParkingSpot, on_delete=models.CASCADE, verbose_name="Парковочное место")
    entry_time = models.DateTimeField(verbose_name="Время въезда")
    exit_time = models.DateTimeField(null=True, blank=True, verbose_name="Время выезда")
    is_reservation = models.BooleanField(default=False, verbose_name="Резервация")
    reservation_start = models.DateTimeField(null=True, blank=True, verbose_name="Начало резервации")
    reservation_end = models.DateTimeField(null=True, blank=True, verbose_name="Конец резервации")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Лог парковки"
        verbose_name_plural = "Логи парковки"
        ordering = ['-entry_time']

    def __str__(self):
        return f"{self.car} - {self.spot} ({self.entry_time})"

    def calculate_duration(self):
        """Расчет длительности парковки"""
        if self.exit_time:
            return self.exit_time - self.entry_time
        return timezone.now() - self.entry_time

class Payment(models.Model):
    """Модель платежа"""
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Ожидает оплаты'),
        ('completed', 'Оплачено'),
        ('failed', 'Ошибка оплаты'),
    ]

    parking_log = models.ForeignKey(ParkingLog, on_delete=models.CASCADE, verbose_name="Лог парковки")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Сумма")
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending', verbose_name="Статус")
    payment_time = models.DateTimeField(null=True, blank=True, verbose_name="Время оплаты")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Платеж"
        verbose_name_plural = "Платежи"
        ordering = ['-created_at']

    def __str__(self):
        return f"Платеж {self.id} - {self.amount} руб."

@receiver(post_migrate)
def create_user_groups(sender, **kwargs):
    """Создание групп пользователей и назначение прав при миграции"""
    if sender.name != 'parking':
        return

    # Создаем группы
    admin_group, _ = Group.objects.get_or_create(name='Administrator')
    receptionist_group, _ = Group.objects.get_or_create(name='Receptionist')
    client_group, _ = Group.objects.get_or_create(name='Client')

    # Получаем все модели приложения
    content_types = ContentType.objects.filter(app_label='parking')
    
    # Права для администратора (все права)
    admin_permissions = Permission.objects.filter(content_type__in=content_types)
    admin_group.permissions.set(admin_permissions)

    # Права для ресепшиониста
    receptionist_permissions = Permission.objects.filter(
        content_type__in=content_types,
        codename__in=[
            'view_parkingspot',
            'view_car',
            'view_parkinglog',
            'view_payment',
        ]
    )
    receptionist_group.permissions.set(receptionist_permissions)

    # Права для клиента
    client_permissions = Permission.objects.filter(
        content_type__in=content_types,
        codename__in=[
            'view_parkingspot',
            'add_parkinglog',
            'view_parkinglog',
            'add_payment',
            'view_payment',
        ]
    )
    client_group.permissions.set(client_permissions)
