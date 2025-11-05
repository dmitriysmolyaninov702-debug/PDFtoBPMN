"""
Hybrid Handler - гибридная обработка (Native + OCR)

Комбинирует нативное извлечение текста с OCR обработкой графических элементов.
Используется когда страница содержит и текстовый слой, и сложную графику.

Стратегия:
1. Извлекаем текст нативно (быстро и точно)
2. Идентифицируем графические элементы (изображения, векторная графика)
3. Отправляем графику в OCR для распознавания
4. Объединяем результаты

Принципы SOLID:
- Single Responsibility: Только гибридная стратегия
- Dependency Inversion: Зависимость от NativeExtractor и OCRClient
"""

import fitz  # PyMuPDF
from typing import List, Dict, Any

from ..models.data_models import (
    TextBlock,
    ImageBlock,
    DrawingBlock,
    TableBlock,
    OCRBlock,
    BBox,
    OCRMode
)
from .native_extractor import NativeExtractor
from .ocr_client import OCRClient


class HybridHandler:
    """
    Гибридный обработчик (Native + OCR)
    
    Ответственность:
    - Координация native extraction и OCR
    - Определение областей для OCR
    - Слияние результатов
    
    Не отвечает за:
    - Построение IR (это делает IRBuilder)
    - Маршрутизацию (это делает ContentRouter)
    """
    
    def __init__(self, 
                 native_extractor: NativeExtractor,
                 ocr_client: OCRClient,
                 ocr_mode: OCRMode = OCRMode.BASE,
                 min_graphic_area: float = 1000.0):
        """
        Инициализация гибридного обработчика
        
        Args:
            native_extractor: Экстрактор для нативного контента
            ocr_client: Клиент для OCR
            ocr_mode: Режим OCR (по умолчанию Base)
            min_graphic_area: Минимальная площадь графики для OCR (px²)
        """
        self.native_extractor = native_extractor
        self.ocr_client = ocr_client
        self.ocr_mode = ocr_mode
        self.min_graphic_area = min_graphic_area
    
    def process_page(self, page: fitz.Page, pdf_path: str = None) -> Dict[str, List]:
        """
        Гибридная обработка страницы
        
        Алгоритм:
        1. Native extraction текста и графики
        2. Фильтрация значимых графических элементов
        3. OCR графических элементов
        4. Возврат комбинированных результатов
        
        Args:
            page: Объект страницы
            pdf_path: Путь к PDF (для таблиц)
        
        Returns:
            Dict с ключами: text_blocks, image_blocks, drawing_blocks, 
                            table_blocks, ocr_blocks
        """
        page_num = page.number
        
        # 1. Нативное извлечение
        native_result = self.native_extractor.extract_page(page, pdf_path)
        
        # 2. Идентификация значимых графических областей
        graphic_regions = self._identify_graphic_regions(
            native_result["image_blocks"],
            native_result["drawing_blocks"]
        )
        
        # 3. OCR графических регионов
        ocr_blocks = []
        for region in graphic_regions:
            try:
                ocr_response = self.ocr_client.ocr_region(
                    page=page,
                    bbox=region["bbox"],
                    mode=self.ocr_mode,
                    prompt=self._get_prompt_for_region(region)
                )
                
                # Добавляем блоки из OCR
                ocr_blocks.extend(ocr_response.blocks)
                
            except Exception as e:
                # Если OCR не удался, пропускаем этот регион
                print(f"⚠️  OCR failed for region on page {page_num}: {e}")
                continue
        
        # 4. Возвращаем комбинированный результат
        return {
            "text_blocks": native_result["text_blocks"],
            "image_blocks": native_result["image_blocks"],
            "drawing_blocks": native_result["drawing_blocks"],
            "table_blocks": native_result["table_blocks"],
            "ocr_blocks": ocr_blocks
        }
    
    def _identify_graphic_regions(self, 
                                  image_blocks: List[ImageBlock],
                                  drawing_blocks: List[DrawingBlock]) -> List[Dict[str, Any]]:
        """
        Идентификация значимых графических областей для OCR
        
        Критерии:
        - Площадь > min_graphic_area
        - Изображения всегда значимы
        - Векторная графика группируется в кластеры
        
        Args:
            image_blocks: Растровые изображения
            drawing_blocks: Векторная графика
        
        Returns:
            Список регионов с bbox и типом
        """
        regions = []
        
        # 1. Все растровые изображения значимы
        for img_block in image_blocks:
            if img_block.bbox.area() >= self.min_graphic_area:
                regions.append({
                    "bbox": img_block.bbox,
                    "type": "image",
                    "metadata": {"xref": img_block.xref}
                })
        
        # 2. Кластеризация векторной графики
        # Простая эвристика: если много drawings близко друг к другу,
        # объединяем их в один регион (возможно диаграмма/схема)
        drawing_clusters = self._cluster_drawings(drawing_blocks)
        
        for cluster in drawing_clusters:
            cluster_bbox = self._merge_bboxes([d.bbox for d in cluster])
            if cluster_bbox.area() >= self.min_graphic_area:
                regions.append({
                    "bbox": cluster_bbox,
                    "type": "drawing",
                    "metadata": {"drawing_count": len(cluster)}
                })
        
        return regions
    
    def _cluster_drawings(self, drawings: List[DrawingBlock]) -> List[List[DrawingBlock]]:
        """
        Кластеризация векторной графики по близости
        
        Простая эвристика: если drawings перекрываются или близки,
        группируем их в один кластер.
        
        Args:
            drawings: Список векторных блоков
        
        Returns:
            Список кластеров (каждый кластер = список DrawingBlock)
        """
        if not drawings:
            return []
        
        # Начинаем с каждого drawing как отдельного кластера
        clusters = [[d] for d in drawings]
        
        # Пороги для слияния кластеров
        OVERLAP_THRESHOLD = 0.1  # 10% перекрытия
        PROXIMITY_THRESHOLD = 20  # 20 пикселей близости
        
        merged = True
        while merged:
            merged = False
            new_clusters = []
            used = set()
            
            for i, cluster1 in enumerate(clusters):
                if i in used:
                    continue
                
                for j, cluster2 in enumerate(clusters[i + 1:], start=i + 1):
                    if j in used:
                        continue
                    
                    # Проверяем, нужно ли объединить кластеры
                    bbox1 = self._merge_bboxes([d.bbox for d in cluster1])
                    bbox2 = self._merge_bboxes([d.bbox for d in cluster2])
                    
                    if self._should_merge_bboxes(bbox1, bbox2, 
                                                 OVERLAP_THRESHOLD, 
                                                 PROXIMITY_THRESHOLD):
                        # Объединяем кластеры
                        cluster1.extend(cluster2)
                        used.add(j)
                        merged = True
                
                new_clusters.append(cluster1)
                used.add(i)
            
            clusters = new_clusters
        
        return clusters
    
    def _merge_bboxes(self, bboxes: List[BBox]) -> BBox:
        """
        Объединить несколько bbox в один (минимальный охватывающий)
        
        Args:
            bboxes: Список bbox
        
        Returns:
            Объединенный bbox
        """
        if not bboxes:
            return BBox(0, 0, 0, 0)
        
        min_x0 = min(b.x0 for b in bboxes)
        min_y0 = min(b.y0 for b in bboxes)
        max_x1 = max(b.x1 for b in bboxes)
        max_y1 = max(b.y1 for b in bboxes)
        
        return BBox(min_x0, min_y0, max_x1, max_y1)
    
    def _should_merge_bboxes(self, bbox1: BBox, bbox2: BBox, 
                            overlap_threshold: float,
                            proximity_threshold: float) -> bool:
        """
        Проверка: нужно ли объединить два bbox
        
        Args:
            bbox1, bbox2: Bbox для проверки
            overlap_threshold: Порог перекрытия (доля от меньшей площади)
            proximity_threshold: Порог близости (пиксели)
        
        Returns:
            bool: True если нужно объединить
        """
        # Проверка перекрытия
        overlap_area = bbox1.overlap_area(bbox2)
        if overlap_area > 0:
            min_area = min(bbox1.area(), bbox2.area())
            if overlap_area / min_area >= overlap_threshold:
                return True
        
        # Проверка близости (минимальное расстояние между краями)
        # Расстояние по X
        dx = 0
        if bbox1.x1 < bbox2.x0:
            dx = bbox2.x0 - bbox1.x1
        elif bbox2.x1 < bbox1.x0:
            dx = bbox1.x0 - bbox2.x1
        
        # Расстояние по Y
        dy = 0
        if bbox1.y1 < bbox2.y0:
            dy = bbox2.y0 - bbox1.y1
        elif bbox2.y1 < bbox1.y0:
            dy = bbox1.y0 - bbox2.y1
        
        distance = (dx ** 2 + dy ** 2) ** 0.5
        return distance <= proximity_threshold
    
    def _get_prompt_for_region(self, region: Dict[str, Any]) -> str:
        """
        Получить промпт для OCR региона в зависимости от типа
        
        Args:
            region: Информация о регионе
        
        Returns:
            Промпт для DeepSeek-OCR
        """
        region_type = region.get("type", "image")
        
        if region_type == "image":
            return (
                "Analyze this image and extract all text, labels, and structural information. "
                "Describe any diagrams, charts, or visual elements in detail."
            )
        elif region_type == "drawing":
            return (
                "This region contains vector graphics (diagrams, formulas, or charts). "
                "Extract all text labels, formulas, and describe the structure. "
                "Preserve mathematical notation if present."
            )
        else:
            return OCRClient.PROMPT_FIGURE_PARSING
    
    def __repr__(self) -> str:
        """Строковое представление"""
        return f"HybridHandler(mode={self.ocr_mode.value})"


