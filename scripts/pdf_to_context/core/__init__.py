"""
Core модули для парсинга и анализа PDF
"""

from .parser import PDFParser
from .analyzer import PageAnalyzer
from .router import ContentRouter
from .structure_preserver import StructurePreserver

__all__ = ["PDFParser", "PageAnalyzer", "ContentRouter", "StructurePreserver"]



