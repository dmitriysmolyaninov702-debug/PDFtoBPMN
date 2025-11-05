"""
Data Models для PDF to Context

Модели данных для представления различных типов контента из PDF.
"""

from .data_models import (
    BBox,
    TextBlock,
    ImageBlock,
    DrawingBlock,
    TableBlock,
    OCRBlock,
    OCRResponse,
    PageMetadata,
    RouteDecision,
    OCRMode,
    LayoutType,
    ContentType,
)

__all__ = [
    "BBox",
    "TextBlock",
    "ImageBlock",
    "DrawingBlock",
    "TableBlock",
    "OCRBlock",
    "OCRResponse",
    "PageMetadata",
    "RouteDecision",
    "OCRMode",
    "LayoutType",
    "ContentType",
]



