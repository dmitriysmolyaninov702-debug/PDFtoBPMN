"""
PDF Parser - базовый парсер PDF файлов

Использует PyMuPDF (fitz) для:
- Открытия PDF файлов
- Итерации по страницам
- Извлечения базовой информации о документе

Принципы SOLID:
- Single Responsibility: Только управление PDF файлом
- Interface Segregation: Минимальный интерфейс для работы с документом
"""

import fitz  # PyMuPDF
import os
import sys
import contextlib
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from ..ir.models import DocumentMetadata


@contextlib.contextmanager
def suppress_stderr():
    """
    Подавление stderr на уровне файловых дескрипторов.
    Работает с низкоуровневыми C-библиотеками (PyMuPDF).
    """
    stderr_fd = sys.stderr.fileno()
    # Сохраняем оригинальный stderr
    with os.fdopen(os.dup(stderr_fd), 'wb') as old_stderr:
        # Перенаправляем stderr в /dev/null
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull_fd, stderr_fd)
        os.close(devnull_fd)
        try:
            yield
        finally:
            # Восстанавливаем stderr
            sys.stderr.flush()
            os.dup2(old_stderr.fileno(), stderr_fd)


class PDFParser:
    """
    Парсер PDF документов на базе PyMuPDF (fitz)
    
    Ответственность:
    - Открытие и закрытие PDF файлов
    - Предоставление доступа к страницам
    - Извлечение метаданных документа
    
    Не отвечает за:
    - Извлечение контента (это делают extractors)
    - Анализ страниц (это делает analyzer)
    - Маршрутизацию (это делает router)
    """
    
    def __init__(self, file_path: str):
        """
        Инициализация парсера
        
        Args:
            file_path: Путь к PDF файлу
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"PDF файл не найден: {file_path}")
        
        if not self.file_path.suffix.lower() == '.pdf':
            raise ValueError(f"Файл должен иметь расширение .pdf: {file_path}")
        
        self.doc: Optional[fitz.Document] = None
        self._is_open = False
    
    def open(self) -> fitz.Document:
        """
        Открыть PDF документ
        
        Returns:
            fitz.Document: Объект документа PyMuPDF
        """
        if self._is_open:
            return self.doc
        
        try:
            # Подавляем предупреждения PyMuPDF на уровне файловых дескрипторов
            with suppress_stderr():
                self.doc = fitz.open(self.file_path)
            
            self._is_open = True
            return self.doc
        except Exception as e:
            raise RuntimeError(f"Ошибка открытия PDF: {e}")
    
    def close(self):
        """Закрыть PDF документ"""
        if self._is_open and self.doc:
            self.doc.close()
            self._is_open = False
            self.doc = None
    
    def __enter__(self):
        """Context manager: вход"""
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager: выход"""
        self.close()
    
    def get_page(self, page_num: int) -> fitz.Page:
        """
        Получить страницу по номеру
        
        Args:
            page_num: Номер страницы (начиная с 0)
        
        Returns:
            fitz.Page: Объект страницы
        """
        if not self._is_open:
            raise RuntimeError("PDF не открыт. Используйте open() или context manager.")
        
        if page_num < 0 or page_num >= len(self.doc):
            raise ValueError(f"Некорректный номер страницы: {page_num} (всего страниц: {len(self.doc)})")
        
        # Подавляем предупреждения при парсинге страницы
        with suppress_stderr():
            return self.doc.load_page(page_num)
    
    def get_total_pages(self) -> int:
        """
        Получить общее количество страниц
        
        Returns:
            int: Количество страниц
        """
        if not self._is_open:
            raise RuntimeError("PDF не открыт")
        
        return len(self.doc)
    
    def extract_metadata(self) -> DocumentMetadata:
        """
        Извлечь метаданные документа
        
        Returns:
            DocumentMetadata: Метаданные документа
        """
        if not self._is_open:
            raise RuntimeError("PDF не открыт")
        
        meta = self.doc.metadata
        
        # Парсинг дат (PyMuPDF возвращает строки в формате PDF)
        creation_date = self._parse_pdf_date(meta.get('creationDate'))
        modification_date = self._parse_pdf_date(meta.get('modDate'))
        
        return DocumentMetadata(
            title=meta.get('title') or self.file_path.stem,
            author=meta.get('author'),
            subject=meta.get('subject'),
            keywords=meta.get('keywords'),
            creator=meta.get('creator'),
            producer=meta.get('producer'),
            creation_date=creation_date,
            modification_date=modification_date,
            source_file=str(self.file_path),
            total_pages=len(self.doc),
            processed_date=datetime.now()
        )
    
    def _parse_pdf_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        Парсинг даты из PDF формата
        
        PDF формат: D:YYYYMMDDHHmmSS+HH'mm'
        Пример: D:20231028120000+03'00'
        
        Args:
            date_str: Строка даты из PDF
        
        Returns:
            datetime или None
        """
        if not date_str:
            return None
        
        try:
            # Убираем префикс D: и временную зону
            date_str = date_str.replace("D:", "")
            date_str = date_str.split("+")[0].split("-")[0]
            
            # Парсим основную часть
            if len(date_str) >= 14:
                return datetime.strptime(date_str[:14], "%Y%m%d%H%M%S")
            elif len(date_str) >= 8:
                return datetime.strptime(date_str[:8], "%Y%m%d")
            else:
                return None
        except Exception:
            return None
    
    def get_page_info(self, page_num: int) -> Dict[str, Any]:
        """
        Получить информацию о странице
        
        Args:
            page_num: Номер страницы (начиная с 0)
        
        Returns:
            Dict с информацией о странице
        """
        page = self.get_page(page_num)
        rect = page.rect
        
        return {
            "page_num": page_num,
            "width": rect.width,
            "height": rect.height,
            "rotation": page.rotation,
            "has_text": bool(page.get_text().strip()),
            "image_count": len(page.get_images(full=True)),
            "drawing_count": len(page.get_drawings())
        }
    
    def __repr__(self) -> str:
        """Строковое представление"""
        status = "открыт" if self._is_open else "закрыт"
        pages = len(self.doc) if self._is_open else "?"
        return f"PDFParser('{self.file_path.name}', страниц: {pages}, статус: {status})"



