"""
DeepSeek OCR Service - GPU-based OCR (высокая точность)

HTTP клиент для DeepSeek-OCR FastAPI сервиса.

Преимущества:
- Очень высокая точность (95-99%)
- Отлично работает с диаграммами, схемами, таблицами
- Поддержка различных промптов
"""

import requests
from typing import Optional
from .base import OCRService


class DeepSeekOCRService(OCRService):
    """GPU-based OCR через DeepSeek-OCR микросервис"""
    
    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 60):
        """
        Инициализация клиента DeepSeek-OCR
        
        Args:
            base_url: URL DeepSeek-OCR сервиса
            timeout: Таймаут запроса в секундах
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._available = None
    
    def is_available(self) -> bool:
        """Проверка доступности DeepSeek-OCR сервиса"""
        if self._available is not None:
            return self._available
        
        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=5
            )
            self._available = response.status_code == 200
            return self._available
        except Exception:
            self._available = False
            return False
    
    def process_image(self, image_data: bytes, prompt: str = "") -> str:
        """
        OCR через DeepSeek-OCR сервис
        
        Args:
            image_data: Байты изображения
            prompt: Промпт для OCR (используется для выбора prompt_type)
        
        Returns:
            Распознанный текст
        """
        if not self.is_available():
            raise RuntimeError(
                f"DeepSeek-OCR сервис недоступен: {self.base_url}\n"
                "Убедитесь что сервис запущен:\n"
                "python -m uvicorn scripts.pdf_to_context.ocr_service.app:app --host 0.0.0.0 --port 8000"
            )
        
        try:
            # Определение prompt_type из промпта
            prompt_type = self._detect_prompt_type(prompt)
            
            # Подготовка данных для отправки
            files = {
                'file': ('image.png', image_data, 'image/png')
            }
            data = {
                'prompt_type': prompt_type,
                'base_size': 1024,
                'image_size': 1024,
                'crop_mode': False
            }
            
            # Отправка запроса
            response = requests.post(
                f"{self.base_url}/ocr/figure",
                files=files,
                data=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            # Извлечение результата
            result = response.json()
            return result.get('markdown', '')
        
        except requests.exceptions.Timeout:
            raise RuntimeError(f"DeepSeek-OCR timeout после {self.timeout}s")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"DeepSeek-OCR request failed: {e}")
        except Exception as e:
            raise RuntimeError(f"DeepSeek-OCR processing failed: {e}")
    
    def _detect_prompt_type(self, prompt: str) -> str:
        """
        Определение типа промпта из текста
        
        Args:
            prompt: Текст промпта
        
        Returns:
            Один из: 'ocr_simple', 'parse_figure', 'bpmn', 'default'
        """
        prompt_lower = prompt.lower()
        
        if 'ocr' in prompt_lower:
            return 'ocr_simple'
        elif 'parse' in prompt_lower or 'figure' in prompt_lower:
            return 'parse_figure'
        elif 'bpmn' in prompt_lower or 'diagram' in prompt_lower:
            return 'bpmn'
        else:
            return 'default'
    
    def get_service_name(self) -> str:
        return f"DeepSeek-OCR (GPU, {self.base_url})"
    
    def get_service_type(self) -> str:
        return "gpu"


