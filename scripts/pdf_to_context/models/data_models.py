"""
Data Models для PDF to Context Extraction

Модели данных для представления различных типов контента,
извлекаемого из PDF документов.

Принципы SOLID:
- Single Responsibility: Каждая модель отвечает за свой тип данных
- Open/Closed: Легко расширять новыми типами блоков
- Liskov Substitution: Все блоки наследуют общий интерфейс
"""

from dataclasses import dataclass, field
from typing import Tuple, Optional, Dict, Any, List
from enum import Enum


# ============================================================================
# Enums для типизации
# ============================================================================

class ContentType(str, Enum):
    """Типы контента в PDF"""
    TEXT = "text"
    IMAGE = "image"
    VECTOR = "vector"
    TABLE = "table"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    FIGURE = "figure"
    UNKNOWN = "unknown"


class LayoutType(str, Enum):
    """Типы layout страницы"""
    SINGLE_COLUMN = "single_column"
    MULTI_COLUMN = "multi_column"
    COMPLEX = "complex"
    NEWSPAPER = "newspaper"
    UNKNOWN = "unknown"


class OCRMode(str, Enum):
    """Режимы DeepSeek-OCR (по README)"""
    TINY = "Tiny"      # 64 vision tokens
    SMALL = "Small"    # 100 vision tokens
    BASE = "Base"      # 256 vision tokens (рекомендуется)
    LARGE = "Large"    # 400 vision tokens (для плотных страниц)
    GUNDAM = "Gundam"  # Dynamic tiles (для газет/постеров)


class RouteDecision(str, Enum):
    """Решение о маршрутизации контента"""
    NATIVE = "native"    # Извлечь нативно
    OCR = "ocr"          # Отправить в OCR
    HYBRID = "hybrid"    # Комбинация native + OCR


# ============================================================================
# Базовые модели
# ============================================================================

@dataclass
class BBox:
    """
    Bounding Box - координаты элемента на странице
    
    Система координат PDF:
    - Начало (0,0) в левом нижнем углу страницы
    - x0, y0 - левый нижний угол элемента
    - x1, y1 - правый верхний угол элемента
    """
    x0: float
    y0: float
    x1: float
    y1: float
    
    def to_tuple(self) -> Tuple[float, float, float, float]:
        """Преобразование в кортеж"""
        return (self.x0, self.y0, self.x1, self.y1)
    
    def area(self) -> float:
        """Площадь bbox"""
        return (self.x1 - self.x0) * (self.y1 - self.y0)
    
    def overlaps(self, other: 'BBox') -> bool:
        """Проверка пересечения с другим bbox"""
        return not (
            self.x1 < other.x0 or
            self.x0 > other.x1 or
            self.y1 < other.y0 or
            self.y0 > other.y1
        )
    
    def overlap_area(self, other: 'BBox') -> float:
        """Площадь пересечения с другим bbox"""
        if not self.overlaps(other):
            return 0.0
        
        x_overlap = min(self.x1, other.x1) - max(self.x0, other.x0)
        y_overlap = min(self.y1, other.y1) - max(self.y0, other.y0)
        return x_overlap * y_overlap


# ============================================================================
# Блоки контента (для native extraction)
# ============================================================================

@dataclass
class TextBlock:
    """Текстовый блок (из native PDF)"""
    bbox: BBox
    text: str
    page_num: int
    type: ContentType = ContentType.TEXT
    font_name: Optional[str] = None
    font_size: Optional[float] = None
    is_bold: bool = False
    is_italic: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Определение типа текстового блока"""
        if self.font_size and self.font_size > 14:
            self.type = ContentType.HEADING
        else:
            self.type = ContentType.PARAGRAPH


@dataclass
class ImageBlock:
    """Растровое изображение (из PDF)"""
    bbox: BBox
    image_data: bytes
    format: str  # 'png', 'jpeg', etc.
    page_num: int
    type: ContentType = ContentType.IMAGE
    width: Optional[int] = None
    height: Optional[int] = None
    xref: Optional[int] = None  # PyMuPDF reference
    needs_ocr: bool = False  # Флаг: нужно ли обработать через OCR
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DrawingBlock:
    """Векторная графика (линии, фигуры, формулы)"""
    bbox: BBox
    drawing_data: Dict[str, Any]  # Векторные команды из PyMuPDF
    page_num: int
    type: ContentType = ContentType.VECTOR
    image_data: Optional[bytes] = None  # Отрендеренное изображение (для OCR)
    needs_ocr: bool = False  # Флаг: нужно ли обработать через OCR
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TableBlock:
    """Таблица (из pdfplumber или OCR)"""
    bbox: BBox
    html: str  # HTML представление таблицы
    rows: int
    cols: int
    page_num: int
    type: ContentType = ContentType.TABLE
    data: Optional[List[List[str]]] = None  # Табличные данные
    source: str = "native"  # "native" | "ocr"
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# OCR модели
# ============================================================================

@dataclass
class OCRBlock:
    """Блок из OCR (DeepSeek-OCR результат)"""
    id: str
    type: ContentType
    content: str  # Markdown или HTML
    bbox: BBox
    page_num: int
    confidence: float  # 0.0 - 1.0
    source: str = "ocr"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OCRResponse:
    """Ответ от DeepSeek-OCR микросервиса"""
    markdown: str
    blocks: List[OCRBlock]
    page_id: int
    vision_tokens_used: int
    text_tokens_generated: int
    mode: OCRMode
    confidence_avg: float


# ============================================================================
# Метаданные страницы
# ============================================================================

@dataclass
class PageMetadata:
    """Метаданные страницы PDF"""
    page_num: int
    width: float
    height: float
    rotation: int
    has_text_layer: bool
    text_density: int  # Примерное количество символов/токенов
    layout_type: LayoutType
    image_count: int
    drawing_count: int
    table_count: int
    bbox_coverage: float  # % площади страницы занятой графикой


# ============================================================================
# Вспомогательные модели
# ============================================================================

@dataclass
class RouteDecisionInfo:
    """Информация о решении маршрутизации"""
    decision: RouteDecision
    ocr_mode: Optional[OCRMode] = None
    reason: str = ""
    metadata: PageMetadata = None



