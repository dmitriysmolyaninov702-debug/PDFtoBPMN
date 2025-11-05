"""
PDF to Context Extraction Module

Модуль для извлечения полного контекста из PDF документов
с поддержкой комбинированного содержимого (текст + графика).

Использует:
- Нативный парсинг для текстовых элементов (PyMuPDF)
- DeepSeek-OCR микросервис для графических/сложных элементов
- IR (Intermediate Representation) как единое промежуточное представление
- Экспорт в структурированный Markdown

Основные компоненты:
- PDFParser: Управление PDF файлами
- ContentRouter: Маршрутизация контента (native/OCR/hybrid)
- IRBuilder: Построение промежуточного представления
- MarkdownFormatter: Форматирование в Markdown
"""

__version__ = "0.1.0"
__author__ = "ПАО «Авиакомпания «ЮТэйр»"

from .pipeline import PDFToContextPipeline

__all__ = ["PDFToContextPipeline"]



