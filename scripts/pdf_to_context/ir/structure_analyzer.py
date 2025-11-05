"""
Structure Analyzer - анализ структуры документа в IR

Определяет:
- Заголовки разных уровней (H1, H2, H3...)
- Параграфы
- Списки (маркированные и нумерованные)
- Иерархию элементов

Используется для улучшения Markdown вывода и потенциального построения BPMN.

Принципы SOLID:
- Single Responsibility: Только анализ структуры
- Open/Closed: Легко добавлять новые эвристики
"""

import re
from typing import List, Dict, Any, Optional, Set
from collections import defaultdict

from .models import IR, IRBlock, IRRelation
from ..models.data_models import ContentType


class StructureAnalyzer:
    """
    Анализатор структуры документа
    
    Ответственность:
    - Определение уровней заголовков
    - Идентификация списков
    - Построение иерархии разделов
    - Улучшение типизации блоков
    
    Не отвечает за:
    - Извлечение контента (это делают extractors)
    - Построение IR (это делает IRBuilder)
    - Форматирование (это делает MarkdownFormatter)
    """
    
    # Паттерны для идентификации структуры
    HEADING_PATTERNS = [
        r'^\d+\.\s+',  # "1. Заголовок"
        r'^\d+\.\d+\s+',  # "1.1 Заголовок"
        r'^[A-ZА-Я][A-ZА-Я\s]+$',  # "ЗАГОЛОВОК ЗАГЛАВНЫМИ"
        r'^Глава\s+\d+',  # "Глава 1"
        r'^Раздел\s+\d+',  # "Раздел 1"
        r'^Приложение\s+[A-ZА-Я\d]',  # "Приложение А"
    ]
    
    LIST_PATTERNS = [
        r'^[-•·]\s+',  # Маркированный список
        r'^\d+\)\s+',  # Нумерованный список "1) "
        r'^[а-я]\)\s+',  # Буквенный список "а) "
        r'^[ivxlcdm]+\)\s+',  # Римские цифры "i) "
    ]
    
    def __init__(self):
        """Инициализация анализатора"""
        pass
    
    def analyze(self, ir: IR) -> IR:
        """
        Анализировать структуру IR и обогатить метаданными
        
        Args:
            ir: Промежуточное представление
        
        Returns:
            IR: Обогащенное IR с улучшенной типизацией и метаданными
        """
        # 1. Определение заголовков
        self._identify_headings(ir)
        
        # 2. Идентификация списков
        self._identify_lists(ir)
        
        # 3. Построение иерархии
        self._build_hierarchy(ir)
        
        # 4. Определение оглавления (TOC)
        toc = self._build_toc(ir)
        ir.document_metadata.processing_stats["toc"] = toc
        
        return ir
    
    def _identify_headings(self, ir: IR):
        """
        Идентификация заголовков и определение их уровней
        
        Эвристики:
        - Размер шрифта (больше среднего → заголовок)
        - Жирный шрифт + короткий текст
        - Паттерны нумерации ("1.", "1.1", etc.)
        - Текст заглавными буквами
        
        Модифицирует блоки в IR in-place.
        """
        # Вычисляем средний размер шрифта для текстовых блоков
        font_sizes = []
        for block in ir.blocks:
            if block.type in [ContentType.TEXT, ContentType.PARAGRAPH]:
                font_size = block.metadata.get("font_size")
                if font_size:
                    font_sizes.append(font_size)
        
        avg_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 12.0
        large_font_threshold = avg_font_size * 1.2  # 20% больше среднего
        
        for block in ir.blocks:
            # Только для текстовых блоков
            if block.type not in [ContentType.TEXT, ContentType.PARAGRAPH, ContentType.HEADING]:
                continue
            
            text = block.content.strip()
            font_size = block.metadata.get("font_size", avg_font_size)
            is_bold = block.metadata.get("is_bold", False)
            
            # Проверяем эвристики
            is_heading = False
            heading_level = 1
            
            # Эвристика 1: Паттерны заголовков
            for pattern in self.HEADING_PATTERNS:
                if re.match(pattern, text):
                    is_heading = True
                    # Определяем уровень по глубине нумерации
                    if re.match(r'^\d+\.\d+\.\d+', text):
                        heading_level = 3
                    elif re.match(r'^\d+\.\d+', text):
                        heading_level = 2
                    elif re.match(r'^\d+\.', text):
                        heading_level = 1
                    break
            
            # Эвристика 2: Большой шрифт
            if font_size > large_font_threshold:
                is_heading = True
                # Уровень зависит от размера
                if font_size > avg_font_size * 1.5:
                    heading_level = 1
                elif font_size > avg_font_size * 1.3:
                    heading_level = 2
                else:
                    heading_level = 3
            
            # Эвристика 3: Жирный + короткий текст
            if is_bold and len(text) < 100:
                is_heading = True
                heading_level = min(heading_level, 2)  # Не выше H2
            
            # Обновляем тип блока
            if is_heading:
                block.type = ContentType.HEADING
                block.metadata["heading_level"] = heading_level
                block.metadata["original_type"] = "heading"
    
    def _identify_lists(self, ir: IR):
        """
        Идентификация списков в документе
        
        Группирует последовательные блоки, начинающиеся с маркеров списка.
        """
        list_id_counter = 0
        current_list_id = None
        
        for i, block in enumerate(ir.blocks):
            if block.type not in [ContentType.TEXT, ContentType.PARAGRAPH]:
                current_list_id = None
                continue
            
            text = block.content.strip()
            
            # Проверяем паттерны списка
            is_list_item = False
            list_type = None
            
            for pattern in self.LIST_PATTERNS:
                if re.match(pattern, text):
                    is_list_item = True
                    if pattern.startswith(r'^\d+'):
                        list_type = "ordered"
                    else:
                        list_type = "unordered"
                    break
            
            if is_list_item:
                # Если это первый элемент нового списка
                if current_list_id is None:
                    list_id_counter += 1
                    current_list_id = f"list_{list_id_counter}"
                
                # Помечаем блок как элемент списка
                block.type = ContentType.LIST
                block.metadata["list_id"] = current_list_id
                block.metadata["list_type"] = list_type
                block.metadata["original_type"] = "list_item"
            else:
                # Список закончился
                current_list_id = None
    
    def _build_hierarchy(self, ir: IR):
        """
        Построение иерархии документа
        
        Определяет родительские и дочерние элементы для заголовков.
        """
        heading_stack = []  # Стек заголовков (level, block_id)
        
        for block in ir.blocks:
            if block.type == ContentType.HEADING:
                level = block.metadata.get("heading_level", 1)
                
                # Находим родительский заголовок
                parent_id = None
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                
                if heading_stack:
                    parent_id = heading_stack[-1][1]
                    block.metadata["parent_heading"] = parent_id
                
                # Добавляем в стек
                heading_stack.append((level, block.id))
            
            # Для всех блоков запоминаем текущий родительский заголовок
            if heading_stack and block.type != ContentType.HEADING:
                block.metadata["parent_heading"] = heading_stack[-1][1]
    
    def _build_toc(self, ir: IR) -> List[Dict[str, Any]]:
        """
        Построение оглавления (Table of Contents)
        
        Returns:
            Список элементов TOC
        """
        toc = []
        
        for block in ir.blocks:
            if block.type == ContentType.HEADING:
                level = block.metadata.get("heading_level", 1)
                text = block.content.strip()
                
                toc.append({
                    "level": level,
                    "text": text,
                    "block_id": block.id,
                    "page": block.page
                })
        
        return toc
    
    def get_sections(self, ir: IR) -> List[Dict[str, Any]]:
        """
        Получить список разделов документа
        
        Args:
            ir: Промежуточное представление
        
        Returns:
            Список разделов с блоками
        """
        sections = []
        current_section = None
        
        for block in ir.blocks:
            if block.type == ContentType.HEADING:
                # Начинаем новую секцию
                if current_section:
                    sections.append(current_section)
                
                current_section = {
                    "heading": block.content.strip(),
                    "heading_block_id": block.id,
                    "level": block.metadata.get("heading_level", 1),
                    "page": block.page,
                    "blocks": []
                }
            elif current_section:
                # Добавляем блок в текущую секцию
                current_section["blocks"].append(block)
        
        # Добавляем последнюю секцию
        if current_section:
            sections.append(current_section)
        
        return sections
    
    def get_lists(self, ir: IR) -> Dict[str, List[IRBlock]]:
        """
        Получить все списки из документа
        
        Args:
            ir: Промежуточное представление
        
        Returns:
            Словарь {list_id: [IRBlock, ...]}
        """
        lists = defaultdict(list)
        
        for block in ir.blocks:
            if block.type == ContentType.LIST:
                list_id = block.metadata.get("list_id")
                if list_id:
                    lists[list_id].append(block)
        
        return dict(lists)
    
    def __repr__(self) -> str:
        """Строковое представление"""
        return "StructureAnalyzer()"


