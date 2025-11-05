"""
Page Analyzer - анализ характеристик страниц PDF

Определяет:
- Плотность текста (количество символов/токенов)
- Тип layout (single/multi-column/complex)
- Наличие текстового слоя
- Покрытие страницы графикой

Эти данные используются ContentRouter для принятия решения
о маршрутизации (native/OCR/hybrid).

Принципы SOLID:
- Single Responsibility: Только анализ характеристик страницы
- Open/Closed: Легко добавлять новые эвристики анализа
"""

import fitz  # PyMuPDF
from typing import List, Tuple
import re

from ..models.data_models import PageMetadata, LayoutType


class PageAnalyzer:
    """
    Анализатор характеристик страниц PDF
    
    Ответственность:
    - Оценка плотности текста
    - Определение типа layout
    - Анализ распределения контента
    - Формирование PageMetadata
    
    Не отвечает за:
    - Извлечение контента (это делают extractors)
    - Маршрутизацию (это делает router)
    """
    
    # Эвристики для анализа
    SINGLE_COLUMN_THRESHOLD = 0.7  # 70% текста в одной колонке
    MULTI_COLUMN_GAP = 50  # Минимальный зазор между колонками (пикселей)
    HIGH_DENSITY_CHARS = 2000  # Порог "высокой плотности" текста
    TOKEN_ESTIMATE_RATIO = 0.25  # Примерное соотношение токенов к символам
    
    def __init__(self):
        """Инициализация анализатора"""
        pass
    
    def analyze_page(self, page: fitz.Page) -> PageMetadata:
        """
        Полный анализ страницы
        
        Args:
            page: Объект страницы PyMuPDF
        
        Returns:
            PageMetadata: Метаданные страницы
        """
        rect = page.rect
        page_num = page.number
        
        # Извлечение базовой информации
        text = page.get_text()
        has_text_layer = bool(text.strip())
        text_density = self.estimate_text_density(page)
        
        # Анализ layout
        layout_type = self.detect_layout_type(page)
        
        # Подсчет графических элементов
        images = page.get_images(full=True)
        drawings = page.get_drawings()
        
        # Оценка покрытия графикой
        bbox_coverage = self.calculate_bbox_coverage(page)
        
        return PageMetadata(
            page_num=page_num,
            width=rect.width,
            height=rect.height,
            rotation=page.rotation,
            has_text_layer=has_text_layer,
            text_density=text_density,
            layout_type=layout_type,
            image_count=len(images),
            drawing_count=len(drawings),
            table_count=0,  # Будет определено позже в extractors
            bbox_coverage=bbox_coverage
        )
    
    def estimate_text_density(self, page: fitz.Page) -> int:
        """
        Оценка плотности текста на странице
        
        Возвращает примерное количество текстовых токенов.
        Используется для решения о выборе OCR режима (Base/Large/Gundam).
        
        Args:
            page: Объект страницы
        
        Returns:
            int: Примерное количество токенов
        """
        text = page.get_text()
        
        # Очистка текста
        text = text.strip()
        if not text:
            return 0
        
        # Подсчет символов
        char_count = len(text)
        
        # Оценка токенов (примерно 4 символа = 1 токен для русского/английского)
        # Для более точной оценки можно использовать tiktoken, но это избыточно
        estimated_tokens = int(char_count * self.TOKEN_ESTIMATE_RATIO)
        
        return estimated_tokens
    
    def detect_layout_type(self, page: fitz.Page) -> LayoutType:
        """
        Определение типа layout страницы
        
        Типы:
        - SINGLE_COLUMN: Одна колонка текста
        - MULTI_COLUMN: Несколько колонок (газеты, журналы)
        - COMPLEX: Сложный layout с множеством элементов
        - NEWSPAPER: Газетный стиль (частный случай multi-column)
        
        Args:
            page: Объект страницы
        
        Returns:
            LayoutType: Тип layout
        """
        # Получаем текстовые блоки с координатами
        text_dict = page.get_text("dict")
        blocks = text_dict.get("blocks", [])
        
        if not blocks:
            return LayoutType.UNKNOWN
        
        # Анализ распределения блоков по X
        text_blocks = [b for b in blocks if b.get("type") == 0]  # 0 = текст
        if len(text_blocks) < 2:
            return LayoutType.SINGLE_COLUMN
        
        # Получаем X координаты всех текстовых блоков
        x_coords = []
        for block in text_blocks:
            bbox = block.get("bbox")
            if bbox:
                x_coords.append((bbox[0], bbox[2]))  # (x0, x1)
        
        if not x_coords:
            return LayoutType.UNKNOWN
        
        # Определяем колонки методом кластеризации
        columns = self._detect_columns(x_coords, page.rect.width)
        
        if len(columns) == 1:
            return LayoutType.SINGLE_COLUMN
        elif len(columns) == 2:
            return LayoutType.MULTI_COLUMN
        elif len(columns) >= 3:
            # Много колонок + много блоков = газетный стиль
            if len(text_blocks) > 10:
                return LayoutType.NEWSPAPER
            else:
                return LayoutType.COMPLEX
        else:
            return LayoutType.SINGLE_COLUMN
    
    def _detect_columns(self, x_coords: List[Tuple[float, float]], page_width: float) -> List[Tuple[float, float]]:
        """
        Определение колонок текста по X координатам
        
        Простая эвристика: группируем блоки с перекрывающимися X диапазонами.
        
        Args:
            x_coords: Список (x0, x1) координат блоков
            page_width: Ширина страницы
        
        Returns:
            Список колонок (x_start, x_end)
        """
        if not x_coords:
            return []
        
        # Сортируем по x0
        sorted_coords = sorted(x_coords, key=lambda c: c[0])
        
        columns = []
        current_col = list(sorted_coords[0])  # [x_start, x_end]
        
        for x0, x1 in sorted_coords[1:]:
            # Проверяем, перекрывается ли с текущей колонкой
            if x0 <= current_col[1] + self.MULTI_COLUMN_GAP:
                # Расширяем текущую колонку
                current_col[1] = max(current_col[1], x1)
            else:
                # Начинаем новую колонку
                columns.append(tuple(current_col))
                current_col = [x0, x1]
        
        # Добавляем последнюю колонку
        columns.append(tuple(current_col))
        
        return columns
    
    def calculate_bbox_coverage(self, page: fitz.Page) -> float:
        """
        Рассчитать процент площади страницы, покрытой графикой
        
        Высокий % coverage → больше графических элементов → OCR
        
        Args:
            page: Объект страницы
        
        Returns:
            float: Процент покрытия (0.0 - 1.0)
        """
        page_area = page.rect.width * page.rect.height
        if page_area == 0:
            return 0.0
        
        graphic_area = 0.0
        
        # Учитываем изображения
        images = page.get_images(full=True)
        for img in images:
            try:
                bbox = page.get_image_bbox(img[0])
                if bbox:
                    area = (bbox.x1 - bbox.x0) * (bbox.y1 - bbox.y0)
                    graphic_area += area
            except Exception:
                continue
        
        # Учитываем векторную графику (drawings)
        drawings = page.get_drawings()
        for drawing in drawings:
            rect = drawing.get("rect")
            if rect:
                area = (rect[2] - rect[0]) * (rect[3] - rect[1])
                graphic_area += area
        
        # Ограничиваем максимум 1.0 (может быть overlap)
        coverage = min(graphic_area / page_area, 1.0)
        
        return coverage
    
    def has_text_layer(self, page: fitz.Page) -> bool:
        """
        Проверка наличия текстового слоя на странице
        
        Args:
            page: Объект страницы
        
        Returns:
            bool: True если есть текстовый слой
        """
        text = page.get_text().strip()
        return bool(text)
    
    def is_dense_page(self, page: fitz.Page, threshold: int = None) -> bool:
        """
        Проверка: страница с высокой плотностью текста?
        
        Args:
            page: Объект страницы
            threshold: Порог плотности (по умолчанию HIGH_DENSITY_CHARS)
        
        Returns:
            bool: True если плотность высокая
        """
        if threshold is None:
            threshold = self.HIGH_DENSITY_CHARS
        
        density = self.estimate_text_density(page)
        return density >= threshold
    
    def is_complex_layout(self, page: fitz.Page) -> bool:
        """
        Проверка: сложный layout?
        
        Args:
            page: Объект страницы
        
        Returns:
            bool: True если layout сложный
        """
        layout_type = self.detect_layout_type(page)
        return layout_type in [LayoutType.COMPLEX, LayoutType.NEWSPAPER]
    
    def __repr__(self) -> str:
        """Строковое представление"""
        return "PageAnalyzer()"



