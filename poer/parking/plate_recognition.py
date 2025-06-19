import cv2
import numpy as np
import subprocess
import os
import tempfile
import logging

logger = logging.getLogger(__name__)

class PlateRecognizer:
    def __init__(self, alpr_path=None):
        """
        Инициализация распознавателя номеров
        :param alpr_path: путь к исполняемому файлу alpr (если не указан, используется системный путь)
        """
        self.alpr_path = alpr_path or 'alpr'
        self.confidence_threshold = 80.0  # Порог уверенности в распознавании

    def preprocess_image(self, image):
        """
        Предобработка изображения для улучшения распознавания
        """
        # Конвертация в оттенки серого
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Увеличение контраста
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        
        # Размытие для уменьшения шума
        blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)
        
        return blurred

    def recognize_plate(self, image):
        """
        Распознавание номера на изображении
        :param image: изображение в формате numpy array
        :return: (номер, уверенность) или (None, 0) если номер не распознан
        """
        try:
            # Сохраняем изображение во временный файл
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                cv2.imwrite(temp_file.name, image)
                
                # Запускаем OpenALPR
                cmd = [
                    self.alpr_path,
                    '-c', 'eu',  # Европейский формат номеров
                    '-n', '1',   # Только лучший результат
                    '-j',        # JSON формат вывода
                    temp_file.name
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                # Удаляем временный файл
                os.unlink(temp_file.name)
                
                if result.returncode == 0:
                    # Парсим JSON результат
                    import json
                    data = json.loads(result.stdout)
                    
                    if data['results']:
                        plate = data['results'][0]
                        if plate['confidence'] >= self.confidence_threshold:
                            return plate['plate'], plate['confidence']
                
                return None, 0
                
        except Exception as e:
            logger.error(f"Ошибка при распознавании номера: {str(e)}")
            return None, 0

    def detect_and_recognize(self, image):
        """
        Обнаружение и распознавание номера на изображении
        :param image: изображение в формате numpy array
        :return: (номер, уверенность, координаты) или (None, 0, None)
        """
        # Предобработка изображения
        processed = self.preprocess_image(image)
        
        # Поиск контуров
        contours, _ = cv2.findContours(
            cv2.Canny(processed, 100, 200),
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        best_result = (None, 0, None)
        
        for contour in contours:
            # Фильтрация по размеру контура
            x, y, w, h = cv2.boundingRect(contour)
            if w < 100 or h < 30:  # Минимальные размеры для номера
                continue
                
            # Вырезаем область с номером
            plate_region = image[y:y+h, x:x+w]
            
            # Распознаем номер
            plate_number, confidence = self.recognize_plate(plate_region)
            
            if confidence > best_result[1]:
                best_result = (plate_number, confidence, (x, y, w, h))
        
        return best_result 