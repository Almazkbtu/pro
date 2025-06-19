from django.utils import timezone
from .models import ParkingSpot
import logging

logger = logging.getLogger(__name__)

def check_reservation_timeouts():
    """Проверка и отмена просроченных резерваций"""
    spots = ParkingSpot.objects.filter(is_reserved=True)
    cancelled = []
    
    for spot in spots:
        try:
            if spot.check_reservation_timeout():
                cancelled.append(spot)
                logger.info(f"Отменена резервация места {spot.number} по таймауту")
        except Exception as e:
            logger.error(f"Ошибка при проверке таймаута места {spot.number}: {str(e)}")
    
    return {
        'cancelled_count': len(cancelled),
        'cancelled_spots': [spot.number for spot in cancelled]
    } 