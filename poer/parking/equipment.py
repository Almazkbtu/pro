import cv2
import numpy as np
import requests
from datetime import datetime
from .models import Car, ParkingLog, ParkingSpot
from .plate_recognition import PlateRecognizer
import logging

logger = logging.getLogger(__name__)

class CameraManager:
    def __init__(self, camera_url, username=None, password=None):
        self.camera_url = camera_url
        self.username = username
        self.password = password
        self.cap = None

    def connect(self):
        """Подключение к камере через RTSP"""
        try:
            if self.username and self.password:
                rtsp_url = f"rtsp://{self.username}:{self.password}@{self.camera_url}"
            else:
                rtsp_url = f"rtsp://{self.camera_url}"
            
            self.cap = cv2.VideoCapture(rtsp_url)
            return self.cap.isOpened()
        except Exception as e:
            logger.error(f"Ошибка подключения к камере: {str(e)}")
            return False

    def get_frame(self):
        """Получение кадра с камеры"""
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                return frame
        return None

    def release(self):
        """Освобождение ресурсов камеры"""
        if self.cap:
            self.cap.release()

class BarrierController:
    def __init__(self, controller_url, api_key=None):
        self.controller_url = controller_url
        self.api_key = api_key
        self.headers = {'Authorization': f'Bearer {api_key}'} if api_key else {}

    def open_barrier(self):
        """Открытие шлагбаума"""
        try:
            response = requests.post(
                f"{self.controller_url}/open",
                headers=self.headers,
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Ошибка открытия шлагбаума: {str(e)}")
            return False

    def close_barrier(self):
        """Закрытие шлагбаума"""
        try:
            response = requests.post(
                f"{self.controller_url}/close",
                headers=self.headers,
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Ошибка закрытия шлагбаума: {str(e)}")
            return False

    def get_status(self):
        """Получение статуса шлагбаума"""
        try:
            response = requests.get(
                f"{self.controller_url}/status",
                headers=self.headers,
                timeout=5
            )
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"Ошибка получения статуса шлагбаума: {str(e)}")
            return None

class ParkingSystem:
    def __init__(self, camera_url, barrier_url, camera_credentials=None, barrier_api_key=None, alpr_path=None):
        self.camera = CameraManager(camera_url, **camera_credentials) if camera_credentials else CameraManager(camera_url)
        self.barrier = BarrierController(barrier_url, barrier_api_key)
        self.plate_recognizer = PlateRecognizer(alpr_path)

    def process_vehicle_entry(self):
        """Обработка въезда автомобиля"""
        if not self.camera.connect():
            return False, "Ошибка подключения к камере"

        frame = self.camera.get_frame()
        if frame is None:
            return False, "Не удалось получить кадр с камеры"

        # Распознаем номер
        plate_number, confidence, coords = self.plate_recognizer.detect_and_recognize(frame)
        
        if not plate_number:
            return False, "Не удалось распознать номер автомобиля"

        logger.info(f"Распознан номер {plate_number} с уверенностью {confidence}%")

        try:
            car = Car.objects.get(number=plate_number)
            available_spot = ParkingSpot.objects.filter(is_available=True).first()
            
            if available_spot:
                # Создаем запись о парковке
                parking_log = ParkingLog.objects.create(
                    car=car,
                    spot=available_spot,
                    entry_time=datetime.now()
                )
                available_spot.is_available = False
                available_spot.save()

                # Открываем шлагбаум
                if self.barrier.open_barrier():
                    return True, f"Автомобиль {plate_number} успешно въехал на парковку"
                else:
                    return False, "Ошибка открытия шлагбаума"
            else:
                return False, "Нет свободных мест на парковке"
        except Car.DoesNotExist:
            return False, f"Автомобиль с номером {plate_number} не зарегистрирован"
        finally:
            self.camera.release()

    def process_vehicle_exit(self):
        """Обработка выезда автомобиля"""
        if not self.camera.connect():
            return False, "Ошибка подключения к камере"

        frame = self.camera.get_frame()
        if frame is None:
            return False, "Не удалось получить кадр с камеры"

        # Распознаем номер
        plate_number, confidence, coords = self.plate_recognizer.detect_and_recognize(frame)
        
        if not plate_number:
            return False, "Не удалось распознать номер автомобиля"

        logger.info(f"Распознан номер {plate_number} с уверенностью {confidence}%")

        try:
            car = Car.objects.get(number=plate_number)
            active_log = ParkingLog.objects.filter(car=car, exit_time__isnull=True).first()
            
            if active_log:
                # Обновляем запись о парковке
                active_log.exit_time = datetime.now()
                active_log.save()

                # Освобождаем место
                active_log.spot.is_available = True
                active_log.spot.save()

                # Открываем шлагбаум
                if self.barrier.open_barrier():
                    return True, f"Автомобиль {plate_number} успешно выехал с парковки"
                else:
                    return False, "Ошибка открытия шлагбаума"
            else:
                return False, f"Нет активной парковки для автомобиля {plate_number}"
        except Car.DoesNotExist:
            return False, f"Автомобиль с номером {plate_number} не зарегистрирован"
        finally:
            self.camera.release() 