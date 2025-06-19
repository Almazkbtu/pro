from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from parking.models import ParkingSpot, Car

class Command(BaseCommand):
    help = 'Initialize database with test data'

    def handle(self, *args, **kwargs):
        # Create groups if they don't exist
        admin_group, _ = Group.objects.get_or_create(name='Administrator')
        receptionist_group, _ = Group.objects.get_or_create(name='Receptionist')
        client_group, _ = Group.objects.get_or_create(name='Client')

        # Create test users if they don't exist
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@example.com',
                'is_staff': True,
                'is_superuser': True
            }
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
            admin_user.groups.add(admin_group)

        receptionist_user, created = User.objects.get_or_create(
            username='receptionist',
            defaults={
                'email': 'receptionist@example.com'
            }
        )
        if created:
            receptionist_user.set_password('receptionist123')
            receptionist_user.save()
            receptionist_user.groups.add(receptionist_group)

        client_user, created = User.objects.get_or_create(
            username='client',
            defaults={
                'email': 'client@example.com'
            }
        )
        if created:
            client_user.set_password('client123')
            client_user.save()
            client_user.groups.add(client_group)

        # Create parking spots if they don't exist
        if not ParkingSpot.objects.exists():
            for i in range(1, 11):
                ParkingSpot.objects.create(
                    number=f'A{i}',
                    is_occupied=False,
                    is_reserved=False
                )

        # Create test cars if they don't exist
        if not Car.objects.exists():
            Car.objects.create(
                license_plate='ABC123',
                owner_name='John Doe',
                phone_number='+1234567890'
            )
            Car.objects.create(
                license_plate='XYZ789',
                owner_name='Jane Smith',
                phone_number='+0987654321'
            )

        self.stdout.write(self.style.SUCCESS('Successfully initialized database')) 