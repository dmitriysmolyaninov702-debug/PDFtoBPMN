"""
OCR Client - HTTP клиент для DeepSeek-OCR микросервиса

Взаимодействует с vLLM-based DeepSeek-OCR сервисом через HTTP API.
Отправляет изображения страниц/блоков и получает структурированный Markdown.

HTTP Contracts (из архитектурного анализа):
- POST /ocr/page - OCR всей страницы
- POST /ocr/figure - OCR отдельного графического элемента

Принципы SOLID:
- Single Responsibility: Только HTTP взаимодействие с OCR
- Dependency Inversion: Зависимость от абстракций (OCRMode, OCRResponse)
"""

import requests
import base64
from typing import Optional, Dict, Any, List
import io
from PIL import Image
import fitz  # PyMuPDF

from ..models.data_models import (
    OCRMode,
    OCRResponse,
    OCRBlock,
    BBox,
    ContentType
)


class OCRClient:
    """
    HTTP клиент для DeepSeek-OCR микросервиса
    
    Ответственность:
    - HTTP запросы к OCR сервису
    - Конвертация изображений в base64
    - Парсинг ответов OCR
    - Обработка ошибок и retry логика
    
    Не отвечает за:
    - Извлечение контента из PDF (это делает NativeExtractor)
    - Построение IR (это делает IRBuilder)
    - Решение о маршрутизации (это делает ContentRouter)
    """
    
    # Промпты для DeepSeek-OCR (из README)
    PROMPT_LAYOUT_MARKDOWN = (
        "Convert the entire page/image into Markdown format. "
        "Preserve layout structure: headings, paragraphs, lists, tables, figures. "
        "For tables, use Markdown table syntax. For figures, use ![alt](path)."
    )
    
    PROMPT_FIGURE_PARSING = (
        "Extract and describe the figure/diagram/chart in detail. "
        "Include any text labels, legends, and structural information."
    )
    
    def __init__(self, base_url: str = "http://localhost:8000",
                 timeout: int = 120,
                 max_retries: int = 3):
        """
        Инициализация OCR клиента
        
        Args:
            base_url: URL базового адреса OCR микросервиса
            timeout: Таймаут HTTP запросов (секунды)
            max_retries: Максимальное количество попыток при ошибках
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self._session = requests.Session()
    
    def ocr_page(self, page: fitz.Page, 
                 mode: OCRMode = OCRMode.BASE,
                 prompt: Optional[str] = None) -> OCRResponse:
        """
        OCR всей страницы PDF
        
        Args:
            page: Объект страницы PyMuPDF
            mode: Режим OCR (Tiny/Small/Base/Large/Gundam)
            prompt: Кастомный промпт (по умолчанию PROMPT_LAYOUT_MARKDOWN)
        
        Returns:
            OCRResponse: Результат OCR с Markdown и блоками
        """
        # Рендерим страницу в изображение
        pix = page.get_pixmap(dpi=150)  # 150 DPI для баланса качества/размера
        img_bytes = pix.tobytes("png")
        
        # Кодируем в base64
        img_base64 = base64.b64encode(img_bytes).decode('utf-8')
        
        # Формируем запрос
        payload = {
            "image": img_base64,
            "mode": mode.value,
            "prompt": prompt or self.PROMPT_LAYOUT_MARKDOWN,
            "page_id": page.number
        }
        
        # Отправляем запрос
        response_data = self._make_request("/ocr/page", payload)
        
        # Парсим ответ
        return self._parse_ocr_response(response_data, page.number)
    
    def ocr_image(self, image_data: bytes, 
                  page_num: int,
                  bbox: Optional[BBox] = None,
                  mode: OCRMode = OCRMode.BASE,
                  prompt: Optional[str] = None,
                  prompt_type: str = "default",
                  base_size: int = 1024,
                  image_size: int = 1024,
                  crop_mode: bool = False) -> OCRResponse:
        """
        OCR отдельного изображения/фигуры
        
        Args:
            image_data: Байты изображения (PNG/JPEG)
            page_num: Номер страницы (для метаданных)
            bbox: BBox элемента на странице
            mode: Режим OCR
            prompt: Кастомный промпт (по умолчанию PROMPT_FIGURE_PARSING)
            prompt_type: Тип системного промпта DeepSeek-OCR 
                        ("default", "parse_figure", "describe", "ocr_simple", etc.)
            base_size: Базовое разрешение для обработки (1024 или 1280 для Large mode)
            image_size: Размер окна изображения (обычно равен base_size)
            crop_mode: Включить автообрезку значимых областей (False - безопаснее)
        
        Returns:
            OCRResponse: Результат OCR
        """
        # Новый API использует multipart/form-data вместо JSON
        url = f"{self.base_url}/ocr/figure"
        
        # Подготавливаем файл
        files = {
            'file': ('image.png', io.BytesIO(image_data), 'image/png')
        }
        
        # Параметры для form-data
        data = {
            'prompt_type': prompt_type,
            'base_size': base_size,
            'image_size': image_size,
            'crop_mode': crop_mode
        }
        
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self._session.post(
                    url,
                    files=files,
                    data=data,
                    timeout=self.timeout
                )
                
                # Проверяем статус
                response.raise_for_status()
                
                # Парсим JSON ответ
                response_data = response.json()
                
                # Парсим ответ
                return self._parse_ocr_response(response_data, page_num)
            
            except requests.exceptions.Timeout as e:
                last_error = f"Timeout после {self.timeout}s"
                continue
            
            except requests.exceptions.ConnectionError as e:
                last_error = f"Connection error: {e}"
                continue
            
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code
                if status_code >= 500:
                    last_error = f"Server error {status_code}"
                    continue
                else:
                    raise RuntimeError(f"OCR request failed: {e}")
            
            except Exception as e:
                last_error = f"Unexpected error: {e}"
                continue
        
        raise RuntimeError(
            f"OCR request failed after {self.max_retries} attempts. "
            f"Last error: {last_error}"
        )
    
    def ocr_region(self, page: fitz.Page, bbox: BBox,
                   mode: OCRMode = OCRMode.BASE,
                   prompt: Optional[str] = None) -> OCRResponse:
        """
        OCR отдельной области страницы
        
        Args:
            page: Объект страницы PyMuPDF
            bbox: BBox области для OCR
            mode: Режим OCR
            prompt: Кастомный промпт
        
        Returns:
            OCRResponse: Результат OCR
        """
        # Вырезаем область страницы
        rect = fitz.Rect(*bbox.to_tuple())
        pix = page.get_pixmap(clip=rect, dpi=150)
        img_bytes = pix.tobytes("png")
        
        return self.ocr_image(
            image_data=img_bytes,
            page_num=page.number,
            bbox=bbox,
            mode=mode,
            prompt=prompt
        )
    
    def _make_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Выполнить HTTP запрос к OCR сервису с retry логикой
        
        Args:
            endpoint: Endpoint API (например "/ocr/page")
            payload: JSON payload
        
        Returns:
            Dict с ответом сервера
        
        Raises:
            RuntimeError: При ошибке после всех попыток
        """
        url = f"{self.base_url}{endpoint}"
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = self._session.post(
                    url,
                    json=payload,
                    timeout=self.timeout,
                    headers={"Content-Type": "application/json"}
                )
                
                # Проверяем статус
                response.raise_for_status()
                
                # Парсим JSON
                return response.json()
            
            except requests.exceptions.Timeout as e:
                last_error = f"Timeout после {self.timeout}s"
                continue
            
            except requests.exceptions.ConnectionError as e:
                last_error = f"Connection error: {e}"
                continue
            
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code
                if status_code >= 500:
                    # Server error - можно retry
                    last_error = f"Server error {status_code}"
                    continue
                else:
                    # Client error - retry бесполезен
                    raise RuntimeError(f"OCR request failed: {e}")
            
            except Exception as e:
                last_error = f"Unexpected error: {e}"
                continue
        
        # Если все попытки исчерпаны
        raise RuntimeError(
            f"OCR request failed after {self.max_retries} attempts. "
            f"Last error: {last_error}"
        )
    
    def _parse_ocr_response(self, response_data: Dict[str, Any], 
                           page_num: int) -> OCRResponse:
        """
        Парсинг ответа от OCR сервиса
        
        Новый формат (FastAPI с DeepSeek-OCR):
        {
            "blocks": [
                {
                    "id": "ocr_block_0",
                    "type": "sub_title",
                    "content": "...",
                    "bbox": {"x0": 127, "y0": 134, "x1": 483, "y1": 147},
                    "confidence": 1.0,
                    "metadata": {}
                },
                ...
            ],
            "markdown": "...",
            "raw_output": "..."
        }
        
        Args:
            response_data: JSON ответ от сервиса
            page_num: Номер страницы
        
        Returns:
            OCRResponse
        """
        # Извлекаем основные поля
        markdown = response_data.get("markdown", "")
        blocks_data = response_data.get("blocks", [])
        raw_output = response_data.get("raw_output", "")
        
        # Парсим блоки
        ocr_blocks = []
        confidences = []
        
        for block_data in blocks_data:
            block_id = block_data.get("id", "")
            type_str = block_data.get("type", "paragraph")
            content = block_data.get("content", "")
            bbox_data = block_data.get("bbox", {})
            confidence = block_data.get("confidence", 1.0)
            
            # Парсим bbox (может быть dict или tuple)
            if isinstance(bbox_data, dict):
                bbox = BBox(
                    x0=bbox_data.get("x0", 0),
                    y0=bbox_data.get("y0", 0),
                    x1=bbox_data.get("x1", 0),
                    y1=bbox_data.get("y1", 0)
                )
            else:
                bbox = BBox(*bbox_data)
            
            # Парсим тип контента
            try:
                content_type = ContentType(type_str)
            except ValueError:
                content_type = ContentType.PARAGRAPH
            
            ocr_block = OCRBlock(
                id=block_id,
                type=content_type,
                content=content,
                bbox=bbox,
                page_num=page_num,
                confidence=confidence,
                source="ocr",
                metadata=block_data.get("metadata", {})
            )
            
            ocr_blocks.append(ocr_block)
            confidences.append(confidence)
        
        # Средняя уверенность
        avg_confidence = sum(confidences) / len(confidences) if confidences else 1.0
        
        # Оценка токенов из raw_output
        vision_tokens = len(raw_output.split()) // 2  # примерная оценка
        text_tokens = len(markdown.split())
        
        return OCRResponse(
            markdown=markdown,
            blocks=ocr_blocks,
            page_id=page_num,
            vision_tokens_used=vision_tokens,
            text_tokens_generated=text_tokens,
            mode=OCRMode.BASE,
            confidence_avg=avg_confidence
        )
    
    def ocr_figure(self, image_data: bytes,
                   page_num: int,
                   bbox: Optional[BBox] = None,
                   prompt_type: str = "default",
                   base_size: int = 1024,
                   image_size: int = 1024) -> OCRResponse:
        """
        Алиас для ocr_image для совместимости с StructurePreserver
        
        Args:
            image_data: Байты изображения
            page_num: Номер страницы
            bbox: BBox элемента (опционально)
            prompt_type: Тип системного промпта ("default", "parse_figure" для BPMN, etc.)
            base_size: Базовое разрешение (1024 или 1280)
            image_size: Размер окна (обычно равен base_size)
        
        Returns:
            OCRResponse
        """
        return self.ocr_image(
            image_data, 
            page_num, 
            bbox,
            prompt_type=prompt_type,
            base_size=base_size,
            image_size=image_size,
            crop_mode=False  # crop_mode выключен по умолчанию (CUDA errors)
        )
    
    def health_check(self) -> bool:
        """
        Проверка доступности OCR сервиса
        
        Returns:
            bool: True если сервис доступен
        """
        try:
            response = self._session.get(
                f"{self.base_url}/health",
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False
    
    def close(self):
        """Закрыть HTTP сессию"""
        self._session.close()
    
    def __enter__(self):
        """Context manager: вход"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager: выход"""
        self.close()
    
    def __repr__(self) -> str:
        """Строковое представление"""
        return f"OCRClient(base_url={self.base_url})"


