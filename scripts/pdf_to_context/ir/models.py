"""
IR (Intermediate Representation) Models

Промежуточное представление документа - единая структура,
объединяющая результаты native extraction и OCR.

Принципы:
- Единое представление для разных источников
- Сохранение метаданных (source, confidence, bbox)
- Поддержка связей между блоками
- Удобство для дальнейшей обработки (BPMN, Markdown, etc.)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime

from ..models.data_models import BBox, ContentType


# ============================================================================
# IR Block - единый блок контента
# ============================================================================

@dataclass
class IRBlock:
    """
    Блок в промежуточном представлении (IR)
    
    Объединяет результаты из:
    - Native extraction (PyMuPDF, pdfplumber)
    - OCR (DeepSeek-OCR)
    
    Attributes:
        id: Уникальный идентификатор блока
        type: Тип контента (heading, paragraph, table, image, etc.)
        content: Содержимое (текст, HTML, markdown, или base64 для изображений)
        page: Номер страницы (начиная с 1)
        bbox: Координаты на странице
        source: Источник данных ("native" | "ocr")
        confidence: Уверенность (для OCR: 0.0-1.0, для native: None)
        metadata: Дополнительные данные (font_size, colors, etc.)
    """
    id: str
    type: ContentType
    content: str
    page: int
    bbox: BBox
    source: str  # "native" | "ocr"
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_from_ocr(self) -> bool:
        """Проверка: блок из OCR"""
        return self.source == "ocr"
    
    def is_high_confidence(self, threshold: float = 0.9) -> bool:
        """Проверка высокой уверенности"""
        if self.confidence is None:
            return True  # native всегда считаем высокой уверенностью
        return self.confidence >= threshold
    
    def get_position_key(self) -> Tuple[int, float, float]:
        """Ключ для сортировки по позиции (page, y, x)"""
        return (self.page, -self.bbox.y1, self.bbox.x0)


# ============================================================================
# IR Relation - связи между блоками
# ============================================================================

@dataclass
class IRRelation:
    """
    Связь между блоками в IR
    
    Типы связей:
    - reading_order: Порядок чтения (следующий блок)
    - caption_of: Подпись к элементу (рисунку, таблице)
    - nested_in: Вложенность (элемент внутри другого)
    - reference: Ссылка (см. рис. 1, табл. 2)
    """
    type: str  # reading_order, caption_of, nested_in, reference
    from_id: str
    to_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Document Metadata
# ============================================================================

@dataclass
class DocumentMetadata:
    """Метаданные всего документа"""
    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    keywords: Optional[str] = None
    creator: Optional[str] = None
    producer: Optional[str] = None
    creation_date: Optional[datetime] = None
    modification_date: Optional[datetime] = None
    
    # Наши метаданные
    source_file: Optional[str] = None
    total_pages: int = 0
    processed_date: datetime = field(default_factory=datetime.now)
    processing_stats: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для frontmatter"""
        result = {}
        
        if self.title:
            result["title"] = self.title
        if self.author:
            result["author"] = self.author
        if self.subject:
            result["subject"] = self.subject
        if self.keywords:
            result["keywords"] = self.keywords
        
        result["source"] = self.source_file
        result["pages"] = self.total_pages
        result["processed"] = self.processed_date.strftime("%Y-%m-%d %H:%M:%S")
        
        if self.processing_stats:
            result["stats"] = self.processing_stats
        
        return result


# ============================================================================
# IR - главная структура
# ============================================================================

@dataclass
class IR:
    """
    Intermediate Representation - промежуточное представление документа
    
    Центральная структура данных, объединяющая:
    - Блоки контента (текст, изображения, таблицы)
    - Связи между блоками (reading order, captions)
    - Метаданные документа
    
    Используется как источник для:
    - Генерации Markdown
    - Построения BPMN (в будущем)
    - Других форматов вывода
    """
    blocks: List[IRBlock]
    relations: List[IRRelation]
    document_metadata: DocumentMetadata
    
    def __post_init__(self):
        """Валидация и индексация после создания"""
        self._index_blocks()
    
    def _index_blocks(self):
        """Создание индекса блоков по ID"""
        self._blocks_by_id = {block.id: block for block in self.blocks}
        self._blocks_by_page = {}
        for block in self.blocks:
            if block.page not in self._blocks_by_page:
                self._blocks_by_page[block.page] = []
            self._blocks_by_page[block.page].append(block)
    
    def get_block(self, block_id: str) -> Optional[IRBlock]:
        """Получить блок по ID"""
        return self._blocks_by_id.get(block_id)
    
    def get_blocks_by_page(self, page: int) -> List[IRBlock]:
        """Получить все блоки на странице"""
        return self._blocks_by_page.get(page, [])
    
    def get_blocks_by_type(self, content_type: ContentType) -> List[IRBlock]:
        """Получить все блоки заданного типа"""
        return [b for b in self.blocks if b.type == content_type]
    
    def get_reading_order(self) -> List[IRBlock]:
        """Получить блоки в порядке чтения"""
        # Сортируем по странице, затем по Y (сверху вниз), затем по X
        return sorted(self.blocks, key=lambda b: b.get_position_key())
    
    def get_ocr_blocks(self) -> List[IRBlock]:
        """Получить все блоки из OCR"""
        return [b for b in self.blocks if b.is_from_ocr()]
    
    def get_native_blocks(self) -> List[IRBlock]:
        """Получить все native блоки"""
        return [b for b in self.blocks if not b.is_from_ocr()]
    
    def get_low_confidence_blocks(self, threshold: float = 0.9) -> List[IRBlock]:
        """Получить блоки с низкой уверенностью"""
        return [b for b in self.blocks if not b.is_high_confidence(threshold)]
    
    def get_relations_from(self, block_id: str) -> List[IRRelation]:
        """Получить все связи, исходящие от блока"""
        return [r for r in self.relations if r.from_id == block_id]
    
    def get_relations_to(self, block_id: str) -> List[IRRelation]:
        """Получить все связи, входящие в блок"""
        return [r for r in self.relations if r.to_id == block_id]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получить статистику по IR"""
        stats = {
            "total_blocks": len(self.blocks),
            "total_relations": len(self.relations),
            "pages": self.document_metadata.total_pages,
            "blocks_by_type": {},
            "blocks_by_source": {
                "native": len(self.get_native_blocks()),
                "ocr": len(self.get_ocr_blocks())
            },
            "low_confidence_blocks": len(self.get_low_confidence_blocks())
        }
        
        # Подсчет блоков по типам
        for block in self.blocks:
            type_name = block.type.value
            stats["blocks_by_type"][type_name] = stats["blocks_by_type"].get(type_name, 0) + 1
        
        return stats
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь (для JSON экспорта)"""
        return {
            "document_metadata": self.document_metadata.to_dict(),
            "statistics": self.get_statistics(),
            "blocks": [
                {
                    "id": b.id,
                    "type": b.type.value,
                    "content": b.content,
                    "page": b.page,
                    "bbox": b.bbox.to_tuple(),
                    "source": b.source,
                    "confidence": b.confidence,
                    "metadata": b.metadata
                }
                for b in self.blocks
            ],
            "relations": [
                {
                    "type": r.type,
                    "from": r.from_id,
                    "to": r.to_id,
                    "metadata": r.metadata
                }
                for r in self.relations
            ]
        }



