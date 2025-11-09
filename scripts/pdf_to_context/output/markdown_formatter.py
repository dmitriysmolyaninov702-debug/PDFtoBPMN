"""
Markdown Formatter - форматирование IR в структурированный Markdown

Преобразует промежуточное представление (IR) в читаемый Markdown документ с:
- YAML frontmatter (метаданные)
- Заголовками разных уровней
- Параграфами и списками
- Таблицами
- Изображениями
- Структурированным оглавлением

Принципы SOLID:
- Single Responsibility: Только форматирование в Markdown
- Open/Closed: Легко добавлять новые форматеры для типов контента
"""

import yaml
from typing import List, Dict, Any, Optional
import re

from ..ir.models import IR, IRBlock
from ..models.data_models import ContentType


class MarkdownFormatter:
    """
    Форматер IR в Markdown
    
    Ответственность:
    - Генерация YAML frontmatter
    - Форматирование заголовков
    - Форматирование параграфов, списков, таблиц
    - Вставка изображений
    - Генерация оглавления (опционально)
    
    Не отвечает за:
    - Извлечение контента (это делают extractors)
    - Построение IR (это делает IRBuilder)
    - Анализ структуры (это делает StructureAnalyzer)
    """
    
    def __init__(self, 
                 include_frontmatter: bool = True,
                 include_toc: bool = True,
                 include_page_numbers: bool = True,
                 max_image_size_kb: int = 500):
        """
        Инициализация форматера
        
        Args:
            include_frontmatter: Включать YAML frontmatter с метаданными
            include_toc: Включать оглавление
            include_page_numbers: Показывать номера страниц в комментариях
            max_image_size_kb: Максимальный размер изображения для вставки (KB)
        """
        self.include_frontmatter = include_frontmatter
        self.include_toc = include_toc
        self.include_page_numbers = include_page_numbers
        self.max_image_size_kb = max_image_size_kb
    
    def format(self, ir: IR) -> str:
        """
        Форматировать IR в Markdown
        
        Args:
            ir: Промежуточное представление
        
        Returns:
            Markdown документ (строка)
        """
        parts = []
        
        # 1. YAML Frontmatter
        if self.include_frontmatter:
            frontmatter = self._generate_frontmatter(ir)
            parts.append(frontmatter)
            parts.append("")  # Пустая строка после frontmatter
        
        # 2. Оглавление
        if self.include_toc:
            toc = self._generate_toc(ir)
            if toc:
                parts.append(toc)
                parts.append("")
        
        # 3. Основной контент
        content = self._format_blocks(ir)
        parts.append(content)
        
        return "\n".join(parts)
    
    def _generate_frontmatter(self, ir: IR) -> str:
        """
        Генерация YAML frontmatter с метаданными
        
        Args:
            ir: Промежуточное представление
        
        Returns:
            YAML frontmatter строка
        """
        metadata_dict = ir.document_metadata.to_dict()
        
        # Добавляем статистику IR
        stats = ir.get_statistics()
        metadata_dict["ir_statistics"] = stats
        
        # Форматируем в YAML
        yaml_str = yaml.dump(metadata_dict, 
                            allow_unicode=True, 
                            sort_keys=False,
                            default_flow_style=False)
        
        return f"---\n{yaml_str}---"
    
    def _generate_toc(self, ir: IR) -> str:
        """
        Генерация оглавления (Table of Contents)
        
        Args:
            ir: Промежуточное представление
        
        Returns:
            Markdown оглавление
        """
        toc_data = ir.document_metadata.processing_stats.get("toc", [])
        
        if not toc_data:
            return ""
        
        lines = ["## Оглавление", ""]
        
        for item in toc_data:
            level = item["level"]
            text = item["text"]
            page = item["page"]
            
            # Создаем anchor (якорь) из текста
            anchor = self._text_to_anchor(text)
            
            # Отступ в зависимости от уровня
            indent = "  " * (level - 1)
            
            # Формат: "- [Текст](#anchor) (стр. X)"
            if self.include_page_numbers:
                line = f"{indent}- [{text}](#{anchor}) *(стр. {page})*"
            else:
                line = f"{indent}- [{text}](#{anchor})"
            
            lines.append(line)
        
        return "\n".join(lines)
    
    def _format_blocks(self, ir: IR) -> str:
        """
        Форматирование всех блоков IR в Markdown
        
        Args:
            ir: Промежуточное представление
        
        Returns:
            Markdown контент
        """
        lines = []
        current_page = None
        current_list_id = None
        
        # Получаем блоки в порядке чтения
        reading_order = ir.get_reading_order()
        
        for block in reading_order:
            # Маркер страницы (опционально)
            if self.include_page_numbers and block.page != current_page:
                current_page = block.page
                lines.append("")
                lines.append(f"<!-- Страница {current_page} -->")
                lines.append("")
            
            # Форматируем блок в зависимости от типа
            formatted = self._format_block(block)
            
            if formatted:
                # Управление списками
                block_list_id = block.metadata.get("list_id")
                
                # Если начался новый список
                if block.type == ContentType.LIST and block_list_id != current_list_id:
                    if current_list_id is not None:
                        lines.append("")  # Разделитель между списками
                    current_list_id = block_list_id
                
                # Если список закончился
                if block.type != ContentType.LIST and current_list_id is not None:
                    current_list_id = None
                    lines.append("")  # Пустая строка после списка
                
                lines.append(formatted)
                
                # Пустая строка после блока (кроме списков)
                if block.type != ContentType.LIST:
                    lines.append("")
        
        return "\n".join(lines)
    
    def _format_block(self, block: IRBlock) -> str:
        """
        Форматирование отдельного блока
        
        Args:
            block: IRBlock
        
        Returns:
            Markdown строка
        """
        content_type = block.type
        
        if content_type == ContentType.HEADING:
            return self._format_heading(block)
        
        elif content_type == ContentType.PARAGRAPH:
            return self._format_paragraph(block)
        
        elif content_type == ContentType.LIST:
            return self._format_list_item(block)
        
        elif content_type == ContentType.TABLE:
            return self._format_table(block)
        
        elif content_type == ContentType.IMAGE:
            return self._format_image(block)
        
        elif content_type == ContentType.FIGURE:
            return self._format_figure(block)
        
        elif content_type == ContentType.VECTOR:
            return self._format_vector(block)
        
        else:
            # Fallback: обычный параграф
            return block.content
    
    def _format_heading(self, block: IRBlock) -> str:
        """Форматирование заголовка"""
        level = block.metadata.get("heading_level", 1)
        text = block.content.strip()
        
        # Markdown заголовок: # H1, ## H2, ### H3, etc.
        heading_prefix = "#" * level
        
        # Создаем anchor для ссылок
        anchor = self._text_to_anchor(text)
        
        return f"{heading_prefix} {text} {{#{anchor}}}"
    
    def _format_paragraph(self, block: IRBlock) -> str:
        """Форматирование параграфа"""
        text = block.content.strip()
        
        # Применяем форматирование (жирный, курсив)
        if block.metadata.get("is_bold"):
            text = f"**{text}**"
        if block.metadata.get("is_italic"):
            text = f"*{text}*"
        
        return text
    
    def _format_list_item(self, block: IRBlock) -> str:
        """Форматирование элемента списка"""
        text = block.content.strip()
        list_type = block.metadata.get("list_type", "unordered")
        
        # Удаляем маркеры из оригинального текста
        text = re.sub(r'^[-•·]\s+', '', text)
        text = re.sub(r'^\d+\)\s+', '', text)
        text = re.sub(r'^[а-я]\)\s+', '', text)
        
        if list_type == "ordered":
            return f"1. {text}"
        else:
            return f"- {text}"
    
    def _format_table(self, block: IRBlock) -> str:
        """Форматирование таблицы"""
        # Если таблица уже в HTML, конвертируем в Markdown
        html_content = block.content
        
        # Простая конвертация HTML table → Markdown table
        # (для полноценной конвертации можно использовать библиотеку html2text)
        
        # Если есть табличные данные, используем их
        table_data = block.metadata.get("data")
        if table_data:
            return self._table_data_to_markdown(table_data)
        else:
            # Fallback: возвращаем HTML as-is
            return f"\n{html_content}\n"
    
    def _table_data_to_markdown(self, table_data: List[List[str]]) -> str:
        """Конвертация табличных данных в Markdown table"""
        if not table_data:
            return ""
        
        lines = []
        
        # Заголовок
        header = " | ".join(str(cell) if cell else "" for cell in table_data[0])
        lines.append(f"| {header} |")
        
        # Разделитель
        separator = " | ".join(["---"] * len(table_data[0]))
        lines.append(f"| {separator} |")
        
        # Строки данных
        for row in table_data[1:]:
            row_str = " | ".join(str(cell) if cell else "" for cell in row)
            lines.append(f"| {row_str} |")
        
        return "\n".join(lines)
    
    def _format_image(self, block: IRBlock) -> str:
        """Форматирование изображения"""
        # content содержит data:image URL
        image_url = block.content
        
        # Проверяем размер
        if "base64," in image_url:
            base64_data = image_url.split("base64,")[1]
            size_kb = len(base64_data) * 3 / 4 / 1024  # Примерный размер в KB
            
            if size_kb > self.max_image_size_kb:
                # Слишком большое изображение - не вставляем
                return f"*[Изображение (размер: {size_kb:.1f} KB) - не вставлено]*"
        
        # Вставляем изображение
        alt_text = f"Image from page {block.page}"
        return f"![{alt_text}]({image_url})"
    
    def _format_figure(self, block: IRBlock) -> str:
        """Форматирование фигуры/диаграммы"""
        content = block.content.strip()
        
        # Если контент из OCR, может быть уже в Markdown
        return f"\n{content}\n"
    
    def _format_vector(self, block: IRBlock) -> str:
        """Форматирование векторной графики"""
        # Векторная графика - просто описание
        content = block.content.strip()
        return f"*{content}*"
    
    def _text_to_anchor(self, text: str) -> str:
        """
        Преобразование текста в anchor (якорь) для ссылок
        
        Args:
            text: Исходный текст
        
        Returns:
            anchor строка (lowercase, без спецсимволов)
        """
        # Убираем нумерацию в начале
        text = re.sub(r'^\d+\.?\s*', '', text)
        
        # Lowercase
        anchor = text.lower()
        
        # Заменяем пробелы на дефисы
        anchor = anchor.replace(' ', '-')
        
        # Убираем спецсимволы (кроме дефисов и букв)
        anchor = re.sub(r'[^\w\-]', '', anchor)
        
        return anchor
    
    def save_to_file(self, ir: IR, output_path: str):
        """
        Форматировать IR и сохранить в файл
        
        Args:
            ir: Промежуточное представление
            output_path: Путь к выходному файлу
        """
        markdown = self.format(ir)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown)
    
    def __repr__(self) -> str:
        """Строковое представление"""
        return (f"MarkdownFormatter(frontmatter={self.include_frontmatter}, "
                f"toc={self.include_toc})")
