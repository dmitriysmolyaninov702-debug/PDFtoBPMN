"""
PaddleOCR Service - CPU-based OCR fallback

Использует PaddleOCR от Baidu для распознавания текста на CPU.

Преимущества:
- Быстрый (2-5 сек на CPU)
- Хорошая точность для русского (88-93%)
- Легче чем PyTorch-based решения
"""

import tempfile
import os
from typing import Optional
from .base import OCRService


class PaddleOCRService(OCRService):
    """CPU-based OCR через PaddleOCR (fallback для систем без GPU)"""
    
    def __init__(self, lang: str = 'ru', use_textline_orientation: bool = True):
        """
        Инициализация PaddleOCR
        
        Args:
            lang: Язык распознавания ('ru', 'en', 'ch' и др.)
            use_textline_orientation: Определение ориентации текста (рекомендуется True)
        """
        self.lang = lang
        self.use_textline_orientation = use_textline_orientation
        self._ocr = None
        self._available = self._check_availability()
        self._fatal_error = False  # Флаг критической ошибки (для отключения OCR)
    
    def _check_availability(self) -> bool:
        """Проверка установки PaddleOCR и PaddlePaddle"""
        try:
            from paddleocr import PaddleOCR
            return True
        except ImportError:
            return False
    
    def _lazy_init(self):
        """Ленивая инициализация OCR (загрузка модели при первом использовании)"""
        if self._ocr is None:
            from paddleocr import PaddleOCR
            self._ocr = PaddleOCR(
                use_angle_cls=self.use_textline_orientation,  # Определение ориентации текста
                lang=self.lang
                # PaddleOCR автоматически использует CPU если GPU недоступна
            )
    
    def is_available(self) -> bool:
        return self._available
    
    def process_image(self, image_data: bytes, prompt: str = "") -> str:
        """
        OCR через PaddleOCR (prompt игнорируется)
        
        Args:
            image_data: Байты изображения
            prompt: Игнорируется (не используется в PaddleOCR)
        
        Returns:
            Распознанный текст
        """
        if not self._available:
            raise RuntimeError("PaddleOCR не установлен. Установите: pip install paddlepaddle paddleocr")
        
        # Если была критическая ошибка ранее - не пытаемся обработать
        if self._fatal_error:
            raise RuntimeError("PaddleOCR отключен из-за предыдущей критической ошибки")
        
        # Ленивая инициализация
        self._lazy_init()
        
        # PaddleOCR работает с файлами, создаем временный
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                f.write(image_data)
                temp_path = f.name
            
            # OCR обработка (стандартный метод PaddleOCR)
            # Параметр cls удален в новых версиях - используется use_angle_cls при инициализации
            result = self._ocr.ocr(temp_path)
            
            # Структура result:
            # result = [  # Список страниц (для нас 1 страница)
            #     [  # Список строк текста на странице
            #         [[[x1,y1], [x2,y2], [x3,y3], [x4,y4]], (text, confidence)],
            #         ...
            #     ]
            # ]
            texts = []
            
            if result and isinstance(result, list) and len(result) > 0:
                page_result = result[0]  # Первая (и единственная) страница
                
                if page_result:  # Может быть None если текста нет
                    for line in page_result:
                        if len(line) >= 2:  # line = [coords, (text, confidence)]
                            text_info = line[1]  # (text, confidence)
                            if isinstance(text_info, tuple) and len(text_info) >= 1:
                                text = text_info[0]
                                texts.append(text)
            
            return '\n'.join(texts) if texts else ""
        
        except Exception as e:
            import traceback
            error_msg = f"{type(e).__name__}: {e}"
            
            # Определяем критические ошибки (которые не исправятся на следующей картинке)
            critical_errors = [
                "ModuleNotFoundError",
                "ImportError", 
                "AttributeError",
                "MemoryError"
            ]
            
            if type(e).__name__ in critical_errors:
                self._fatal_error = True
                print(f"   ❌ КРИТИЧЕСКАЯ ОШИБКА PaddleOCR: {error_msg}")
                print(f"   ⚠️  OCR будет отключен для остальных изображений")
            else:
                print(f"   ⚠️  PaddleOCR ошибка (не критична): {error_msg}")
            
            raise RuntimeError(f"PaddleOCR processing failed: {e}")
        
        finally:
            # Удаление временного файла
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except:
                    pass  # Игнорируем ошибки удаления
    
    def get_service_name(self) -> str:
        return f"PaddleOCR (CPU, lang={self.lang})"
    
    def get_service_type(self) -> str:
        return "cpu"

