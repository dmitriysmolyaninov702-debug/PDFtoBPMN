"""
IR (Intermediate Representation) модули
"""

from .models import IR, IRBlock, IRRelation
from .builder import IRBuilder
from .structure_analyzer import StructureAnalyzer

__all__ = ["IR", "IRBlock", "IRRelation", "IRBuilder", "StructureAnalyzer"]



