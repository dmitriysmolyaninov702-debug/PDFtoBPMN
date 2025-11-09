"""
Базовый интерфейс для OCR сервисов

Применение SOLID:
- Interface Segregation: Минимальный интерфейс
- Dependency Inversion: Pipeline зависит от абстракции
- Open/Closed: Легко добавлять новые реализации
"""

from abc import ABC, abstractmethod
from typing import Optional


class OCRService(ABC):
    """Базовый интерфейс для всех OCR сервисов"""
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Проверка доступности сервиса
        
        Returns:
            bool: True если сервис готов к работе
        """
        pass
    
    @abstractmethod
    def process_image(self, image_data: bytes, prompt: str = "") -> str:
        """
        Обработка изображения через OCR
        
        Args:
            image_data: Байты изображения (PNG/JPEG)
            prompt: Подсказка для OCR (используется только в DeepSeek, игнорируется в других)
        
        Returns:
            str: Распознанный текст
            
        Raises:
            RuntimeError: Если обработка не удалась
        """
        pass
    
    @abstractmethod
    def get_service_name(self) -> str:
        """
        Название сервиса для логирования
        
        Returns:
            str: Человекочитаемое название
        """
        pass
    
    @abstractmethod
    def get_service_type(self) -> str:
        """
        Тип сервиса для категоризации
        
        Returns:
            str: "gpu" или "cpu"
        """
        pass


