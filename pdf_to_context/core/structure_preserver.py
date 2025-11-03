"""
Structure Preserver - встраивание OCR результатов в структуру документа

Ключевой компонент новой архитектуры "структура сначала, графика потом".

Ответственность:
- Получение структуры с placeholder'ами для графики (ImageBlock с needs_ocr=True)
- Обработка графических элементов через OCR
- Встраивание OCR результатов по bbox обратно в структуру
- Сохранение оригинального порядка элементов документа

Принципы SOLID:
- Single Responsibility: Только встраивание OCR в структуру
- Open/Closed: Легко добавить новые типы обработки
- Dependency Inversion: Зависит от абстракции OCRClient
"""

from typing import List, Union, Optional
from PIL import Image
import io

from ..models.data_models import (
    TextBlock,
    ImageBlock,
    DrawingBlock,
    TableBlock,
    OCRBlock,
    BBox,
    ContentType
)
from ..extractors.ocr_client import OCRClient


class StructurePreserver:
    """
    Встраивание OCR результатов в структуру документа
    
    Алгоритм:
    1. Получает блоки с placeholder'ами (ImageBlock с needs_ocr=True)
    2. Фильтрует: какие изображения требуют OCR
    3. Для каждого изображения:
       - Обрабатывает через OCR
       - Создает OCRBlock с результатом
       - Заменяет ImageBlock → OCRBlock (сохраняя позицию)
    4. Сортирует все блоки по позиции (page, Y, X)
    5. Возвращает полную структуру с сохранением layout
    """
    
    def __init__(self, ocr_client: Optional[OCRClient] = None, min_area: float = 1000.0):
        """
        Инициализация
        
        Args:
            ocr_client: Клиент для OCR (если None - пропускаем OCR)
            min_area: Минимальная площадь изображения для OCR (px²)
        """
        self.ocr_client = ocr_client
        self.min_area = min_area
        self._stats = {
            "total_images": 0,
            "total_drawings": 0,
            "ocr_processed": 0,
            "ocr_skipped": 0,
            "ocr_errors": 0
        }
    
    def process_structure(
        self,
        blocks: List[Union[TextBlock, ImageBlock, DrawingBlock, TableBlock]],
        page_num: int
    ) -> List[Union[TextBlock, OCRBlock, DrawingBlock, TableBlock]]:
        """
        Обработка структуры страницы
        
        Args:
            blocks: Список блоков с placeholder'ами для графики
            page_num: Номер страницы (для логирования)
        
        Returns:
            Полная структура с встроенными OCR результатами
        """
        processed_blocks = []
        
        for block in blocks:
            # Если это ImageBlock с флагом needs_ocr - обрабатываем через OCR
            if isinstance(block, ImageBlock) and block.needs_ocr:
                self._stats["total_images"] += 1
                
                # Обрабатываем ВСЕ изображения без ограничения по площади
                # (схемы BPMN могут быть любого размера)
                
                # OCR обработка
                ocr_block = self._process_image_ocr(block, page_num)
                
                if ocr_block:
                    self._stats["ocr_processed"] += 1
                    processed_blocks.append(ocr_block)
                else:
                    self._stats["ocr_errors"] += 1
                    # OCR не удался - оставляем оригинальный ImageBlock
                    processed_blocks.append(block)
            
            # DrawingBlock (векторная графика) - полностью игнорируем
            # Векторные примитивы (линии, стрелки, рамки) не нужны в контексте
            elif isinstance(block, DrawingBlock):
                # Пропускаем векторную графику
                continue
            
            else:
                # Текст, таблицы и остальные блоки - оставляем без изменений
                processed_blocks.append(block)
        
        # Сортируем блоки в порядке чтения: страница → Y (сверху вниз) → X (слева направо)
        sorted_blocks = sorted(processed_blocks, key=lambda b: self._get_position_key(b))
        
        return sorted_blocks
    
    def _process_image_ocr(self, image_block: ImageBlock, page_num: int) -> Optional[OCRBlock]:
        """
        Обработка изображения через OCR
        
        Args:
            image_block: Блок изображения
            page_num: Номер страницы
        
        Returns:
            OCRBlock с результатом или None при ошибке
        """
        if not self.ocr_client:
            return None
        
        try:
            # Отправляем в OCR с правильными параметрами для распознавания схем/диаграмм
            ocr_response = self.ocr_client.ocr_figure(
                image_data=image_block.image_data,
                page_num=page_num,
                bbox=image_block.bbox,
                prompt_type="parse_figure",  # Детальное описание диаграмм
                base_size=1024,              # Оптимальный размер для BPMN схем
                image_size=1024
            )
            
            # Если OCR вернул результаты
            if ocr_response and ocr_response.blocks:
                # Объединяем все блоки в один OCRBlock
                combined_content = "\n".join([b.content for b in ocr_response.blocks])
                first_block = ocr_response.blocks[0]
                
                # Создаем OCRBlock
                ocr_block = OCRBlock(
                    id=f"ocr_image_{page_num}_{id(image_block)}",
                    bbox=image_block.bbox,  # Сохраняем оригинальный bbox
                    content=combined_content,
                    page_num=page_num,
                    type=first_block.type,
                    confidence=ocr_response.confidence_avg,
                    metadata={
                        "source": "image_ocr",
                        "original_format": image_block.format,
                        "markdown": ocr_response.markdown,
                        **first_block.metadata
                    }
                )
                
                return ocr_block
            else:
                return None
                
        except Exception as e:
            print(f"⚠️  OCR error for image on page {page_num}: {e}")
            return None
    
    def _process_drawing_ocr(self, drawing_block: DrawingBlock, page_num: int) -> Optional[OCRBlock]:
        """
        Обработка векторной графики через OCR
        
        Args:
            drawing_block: Блок векторной графики с отрендеренным изображением
            page_num: Номер страницы
        
        Returns:
            OCRBlock с результатом или None при ошибке
        """
        if not self.ocr_client or not drawing_block.image_data:
            return None
        
        try:
            # Отправляем отрендеренное изображение в OCR
            # Для векторной графики используем parse_figure - оптимально для BPMN диаграмм
            ocr_response = self.ocr_client.ocr_figure(
                image_data=drawing_block.image_data,
                page_num=page_num,
                bbox=drawing_block.bbox,
                prompt_type="parse_figure",  # Лучший промпт для BPMN/диаграмм
                base_size=1024,              # Базовое разрешение (достаточно для большинства)
                image_size=1024              # Окно обработки
            )
            
            # Если OCR вернул результаты
            if ocr_response and ocr_response.blocks:
                # Объединяем все блоки в один OCRBlock
                combined_content = "\n".join([b.content for b in ocr_response.blocks])
                first_block = ocr_response.blocks[0]
                
                # Создаем OCRBlock
                ocr_block = OCRBlock(
                    id=f"ocr_drawing_{page_num}_{id(drawing_block)}",
                    bbox=drawing_block.bbox,  # Сохраняем оригинальный bbox
                    content=combined_content,
                    page_num=page_num,
                    type=first_block.type,
                    confidence=ocr_response.confidence_avg,
                    metadata={
                        "source": "vector_ocr",
                        "drawing_type": drawing_block.drawing_data.get("type"),
                        "markdown": ocr_response.markdown,
                        **first_block.metadata
                    }
                )
                
                return ocr_block
            else:
                return None
                
        except Exception as e:
            print(f"⚠️  OCR error for drawing on page {page_num + 1}:")
            print(f"    Ошибка: {e}")
            print(f"    BBox: {drawing_block.bbox}")
            print(f"    Площадь: {drawing_block.bbox.area():.0f}px²")
            import traceback
            traceback.print_exc()
            return None
    
    def _get_position_key(self, block) -> tuple:
        """
        Ключ для сортировки блоков по позиции
        
        Args:
            block: Любой блок с bbox и page_num
        
        Returns:
            Кортеж (page, -y1, x0) для сортировки
        """
        # Отрицательный y1 потому что в PDF координаты снизу вверх,
        # а нам нужно сверху вниз
        return (block.page_num, -block.bbox.y1, block.bbox.x0)
    
    def get_statistics(self) -> dict:
        """Получить статистику обработки"""
        return self._stats.copy()
    
    def reset_statistics(self):
        """Сбросить статистику"""
        self._stats = {
            "total_images": 0,
            "total_drawings": 0,
            "ocr_processed": 0,
            "ocr_skipped": 0,
            "ocr_errors": 0
        }
    
    def __repr__(self) -> str:
        """Строковое представление"""
        return (
            f"StructurePreserver("
            f"ocr={'enabled' if self.ocr_client else 'disabled'}, "
            f"min_area={self.min_area})"
        )

