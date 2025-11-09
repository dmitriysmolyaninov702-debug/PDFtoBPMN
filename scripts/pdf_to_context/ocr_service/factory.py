"""
OCR Service Factory - автоматический выбор OCR реализации

Применение SOLID:
- Factory Pattern: Централизованное создание объектов
- Strategy Pattern: Выбор стратегии в runtime
- Dependency Inversion: Возвращаем абстракцию (OCRService)
"""

import torch
from typing import Optional
from .base import OCRService
from .deepseek_service import DeepSeekOCRService
from .paddleocr_service import PaddleOCRService


class OCRServiceFactory:
    """
    Factory для автоматического выбора оптимального OCR сервиса
    
    Логика выбора:
    1. Если CUDA доступна + DeepSeek сервис работает → DeepSeek (GPU, высокая точность)
    2. Если PaddleOCR установлен → PaddleOCR (CPU, хорошая точность)
    3. Иначе → RuntimeError (нет доступных сервисов)
    """
    
    @staticmethod
    def create(
        prefer_deepseek: bool = True,
        deepseek_url: str = "http://localhost:8000",
        paddleocr_lang: str = "ru"
    ) -> OCRService:
        """
        Автоматический выбор OCR сервиса
        
        Args:
            prefer_deepseek: Предпочитать DeepSeek если доступен
            deepseek_url: URL DeepSeek-OCR сервиса
            paddleocr_lang: Язык для PaddleOCR ('ru', 'en', 'ch' и др.)
        
        Returns:
            Экземпляр OCRService (DeepSeek или PaddleOCR)
        
        Raises:
            RuntimeError: Если ни один сервис недоступен
        """
        services_tried = []
        
        # 1. Попытка DeepSeek (если CUDA + prefer)
        if prefer_deepseek and torch.cuda.is_available():
            deepseek = DeepSeekOCRService(base_url=deepseek_url)
            if deepseek.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                print(f"🔍 OCR: {deepseek.get_service_name()}")
                print(f"   GPU: {gpu_name}")
                print(f"   Точность: 95-99% (AI-based)")
                return deepseek
            services_tried.append(f"DeepSeek ({deepseek_url}) - недоступен")
        elif prefer_deepseek and not torch.cuda.is_available():
            services_tried.append("DeepSeek - нет CUDA")
        
        # 2. Fallback: PaddleOCR
        paddle = PaddleOCRService(lang=paddleocr_lang)
        if paddle.is_available():
            print(f"🔍 OCR: {paddle.get_service_name()}")
            print(f"   Режим: CPU")
            print(f"   Точность: 88-93% (rule-based + DL)")
            return paddle
        services_tried.append("PaddleOCR - не установлен")
        
        # 3. Ничего не доступно
        error_msg = (
            "❌ Ни один OCR сервис недоступен!\n\n"
            "Попытки:\n"
        )
        for attempt in services_tried:
            error_msg += f"  - {attempt}\n"
        
        error_msg += (
            "\n"
            "Решения:\n"
            "  1. Установите PaddleOCR (рекомендуется для CPU):\n"
            "     pip install paddlepaddle paddleocr\n\n"
            "  2. Или запустите DeepSeek-OCR сервис (для GPU):\n"
            f"     python -m uvicorn scripts.pdf_to_context.ocr_service.app:app --host 0.0.0.0 --port 8000\n"
        )
        
        raise RuntimeError(error_msg)
    
    @staticmethod
    def create_deepseek_only(deepseek_url: str = "http://localhost:8000") -> OCRService:
        """
        Принудительное использование DeepSeek
        
        Args:
            deepseek_url: URL DeepSeek-OCR сервиса
        
        Returns:
            DeepSeekOCRService
        
        Raises:
            RuntimeError: Если DeepSeek недоступен
        """
        deepseek = DeepSeekOCRService(base_url=deepseek_url)
        if not deepseek.is_available():
            raise RuntimeError(
                f"DeepSeek-OCR сервис недоступен: {deepseek_url}\n"
                "Убедитесь что сервис запущен"
            )
        return deepseek
    
    @staticmethod
    def create_paddleocr_only(lang: str = "ru") -> OCRService:
        """
        Принудительное использование PaddleOCR
        
        Args:
            lang: Язык для распознавания
        
        Returns:
            PaddleOCRService
        
        Raises:
            RuntimeError: Если PaddleOCR не установлен
        """
        paddle = PaddleOCRService(lang=lang)
        if not paddle.is_available():
            raise RuntimeError(
                "PaddleOCR не установлен!\n"
                "Установите: pip install paddlepaddle paddleocr"
            )
        return paddle


