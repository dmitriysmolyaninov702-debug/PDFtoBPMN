"""
Content Router - маршрутизация контента PDF

Принимает решение о способе обработки страницы/блока:
- NATIVE: Извлечь нативно (PyMuPDF + pdfplumber)
- OCR: Отправить в DeepSeek-OCR микросервис
- HYBRID: Комбинация (текст нативно, графика через OCR)

Решение основано на эвристиках из архитектурного анализа:
- Наличие текстового слоя
- Плотность текста (для выбора OCR режима)
- Тип layout (сложность)
- Покрытие графикой

Принципы SOLID:
- Single Responsibility: Только принятие решений о маршрутизации
- Open/Closed: Легко добавлять новые правила маршрутизации
"""

import fitz  # PyMuPDF
from typing import Optional

from ..models.data_models import (
    RouteDecision,
    RouteDecisionInfo,
    OCRMode,
    LayoutType,
    PageMetadata
)
from .analyzer import PageAnalyzer


class ContentRouter:
    """
    Маршрутизатор контента PDF
    
    Ответственность:
    - Принятие решения: native/OCR/hybrid
    - Выбор режима OCR (Base/Large/Gundam)
    - Обоснование решения
    
    Не отвечает за:
    - Извлечение контента (это делают extractors)
    - Анализ страниц (это делает analyzer)
    
    Эвристики маршрутизации (из архитектурного анализа):
    
    NATIVE:
    - Есть текстовый слой
    - Простой layout (single column)
    - Низкое покрытие графикой (< 30%)
    
    OCR:
    - Нет текстового слоя (сканы)
    - Сложный layout (multi-column, newspaper)
    - Высокое покрытие графикой (> 50%)
    - Плотность > 2000 токенов (нужен Base/Large)
    
    HYBRID:
    - Есть текстовый слой, но много embedded картинок/формул
    - Средние показатели
    """
    
    # Пороги для принятия решений (из рекомендаций эксперта)
    BBOX_COVERAGE_LOW = 0.3   # Низкое покрытие графикой
    BBOX_COVERAGE_HIGH = 0.5  # Высокое покрытие графикой
    
    TEXT_DENSITY_HIGH = 2000  # Порог высокой плотности (токены)
    TEXT_DENSITY_VERY_HIGH = 5000  # Очень высокая плотность
    
    # Режимы OCR по плотности (из DeepSeek-OCR README)
    MODE_TINY_MAX = 500       # До 500 токенов → Tiny (64 vision tokens)
    MODE_SMALL_MAX = 1000     # До 1000 токенов → Small (100 vision tokens)
    MODE_BASE_MAX = 2500      # До 2500 токенов → Base (256 vision tokens)
    MODE_LARGE_MAX = 5000     # До 5000 токенов → Large (400 vision tokens)
    # > 5000 токенов → Gundam (dynamic tiles)
    
    def __init__(self, analyzer: Optional[PageAnalyzer] = None, 
                 prioritize_accuracy: bool = True):
        """
        Инициализация роутера
        
        Args:
            analyzer: PageAnalyzer (если None, создастся новый)
            prioritize_accuracy: Приоритет точности над скоростью
                                 (согласовано с пользователем)
        """
        self.analyzer = analyzer or PageAnalyzer()
        self.prioritize_accuracy = prioritize_accuracy
    
    def route_page(self, page: fitz.Page, 
                   metadata: Optional[PageMetadata] = None) -> RouteDecisionInfo:
        """
        Принять решение о маршрутизации страницы
        
        Args:
            page: Объект страницы PyMuPDF
            metadata: PageMetadata (если уже проанализирована)
        
        Returns:
            RouteDecisionInfo: Решение с обоснованием
        """
        # Анализируем страницу, если метаданные не предоставлены
        if metadata is None:
            metadata = self.analyzer.analyze_page(page)
        
        # Применяем правила маршрутизации
        decision, ocr_mode, reason = self._apply_routing_rules(metadata)
        
        return RouteDecisionInfo(
            decision=decision,
            ocr_mode=ocr_mode,
            reason=reason,
            metadata=metadata
        )
    
    def _apply_routing_rules(self, meta: PageMetadata) -> tuple[RouteDecision, Optional[OCRMode], str]:
        """
        Применить правила маршрутизации
        
        Returns:
            (decision, ocr_mode, reason)
        """
        # ПРАВИЛО 1: Нет текстового слоя → OCR
        if not meta.has_text_layer:
            ocr_mode = self._select_ocr_mode(meta.text_density, meta.layout_type)
            return (
                RouteDecision.OCR,
                ocr_mode,
                "Отсутствует текстовый слой (скан или изображение)"
            )
        
        # ПРАВИЛО 2: Газетный layout → OCR Gundam
        if meta.layout_type == LayoutType.NEWSPAPER:
            return (
                RouteDecision.OCR,
                OCRMode.GUNDAM,
                "Газетный layout (multi-column, high density)"
            )
        
        # ПРАВИЛО 3: Сложный layout → OCR
        if meta.layout_type == LayoutType.COMPLEX:
            ocr_mode = self._select_ocr_mode(meta.text_density, meta.layout_type)
            return (
                RouteDecision.OCR,
                ocr_mode,
                f"Сложный layout (тип: {meta.layout_type.value})"
            )
        
        # ПРАВИЛО 4: Высокое покрытие графикой → OCR
        if meta.bbox_coverage > self.BBOX_COVERAGE_HIGH:
            ocr_mode = self._select_ocr_mode(meta.text_density, meta.layout_type)
            return (
                RouteDecision.OCR,
                ocr_mode,
                f"Высокое покрытие графикой ({meta.bbox_coverage:.1%})"
            )
        
        # ПРАВИЛО 5: Средние показатели → HYBRID
        if (meta.bbox_coverage > self.BBOX_COVERAGE_LOW and 
            (meta.image_count > 0 or meta.drawing_count > 5)):
            # Есть текст, но много графики → гибридный подход
            # Приоритет точности: используем OCR для графических элементов
            if self.prioritize_accuracy:
                ocr_mode = self._select_ocr_mode(meta.text_density, meta.layout_type)
                return (
                    RouteDecision.HYBRID,
                    ocr_mode,
                    f"Гибридный: текст нативно, графика через OCR "
                    f"(изображений: {meta.image_count}, векторов: {meta.drawing_count})"
                )
        
        # ПРАВИЛО 6: Очень высокая плотность текста → OCR Large/Gundam
        # (нативный парсинг может терять структуру)
        if self.prioritize_accuracy and meta.text_density > self.TEXT_DENSITY_VERY_HIGH:
            ocr_mode = self._select_ocr_mode(meta.text_density, meta.layout_type)
            return (
                RouteDecision.OCR,
                ocr_mode,
                f"Очень высокая плотность текста ({meta.text_density} токенов), "
                f"OCR сохранит структуру лучше"
            )
        
        # ПРАВИЛО 7 (default): Простой случай → NATIVE
        return (
            RouteDecision.NATIVE,
            None,
            f"Стандартный PDF с текстовым слоем "
            f"(layout: {meta.layout_type.value}, плотность: {meta.text_density} токенов)"
        )
    
    def _select_ocr_mode(self, text_density: int, layout_type: LayoutType) -> OCRMode:
        """
        Выбор режима OCR на основе плотности и layout
        
        Режимы DeepSeek-OCR (из README):
        - Tiny: 64 vision tokens (до ~500 text tokens)
        - Small: 100 vision tokens (до ~1000 text tokens)
        - Base: 256 vision tokens (до ~2500 text tokens) - рекомендуется
        - Large: 400 vision tokens (до ~5000 text tokens)
        - Gundam: Dynamic tiles (для сверхплотных страниц / газет)
        
        Args:
            text_density: Примерное количество токенов
            layout_type: Тип layout страницы
        
        Returns:
            OCRMode: Выбранный режим
        """
        # Газетный layout всегда → Gundam
        if layout_type == LayoutType.NEWSPAPER:
            return OCRMode.GUNDAM
        
        # Приоритет точности: выбираем более мощные режимы
        if self.prioritize_accuracy:
            if text_density <= self.MODE_SMALL_MAX:
                return OCRMode.BASE  # Используем Base вместо Small/Tiny
            elif text_density <= self.MODE_BASE_MAX:
                return OCRMode.BASE  # Рекомендуемый режим
            elif text_density <= self.MODE_LARGE_MAX:
                return OCRMode.LARGE  # Для плотных страниц
            else:
                return OCRMode.GUNDAM  # Для сверхплотных
        else:
            # Баланс скорости и точности
            if text_density <= self.MODE_TINY_MAX:
                return OCRMode.TINY
            elif text_density <= self.MODE_SMALL_MAX:
                return OCRMode.SMALL
            elif text_density <= self.MODE_BASE_MAX:
                return OCRMode.BASE
            elif text_density <= self.MODE_LARGE_MAX:
                return OCRMode.LARGE
            else:
                return OCRMode.GUNDAM
    
    def __repr__(self) -> str:
        """Строковое представление"""
        mode = "accuracy" if self.prioritize_accuracy else "balanced"
        return f"ContentRouter(mode={mode})"



