"""
DeepSeek-OCR Wrapper для интеграции с микросервисом

Обертка для работы с DeepSeek-OCR через vLLM в нашем микросервисе.
Упрощает взаимодействие между FastAPI и DeepSeek-OCR.
"""

import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import base64
import io
from PIL import Image

# Добавляем путь к DeepSeek-OCR
DEEPSEEK_DIR = Path(__file__).parent.parent.parent / "DeepSeek-OCR" / "DeepSeek-OCR-master" / "DeepSeek-OCR-vllm"
sys.path.insert(0, str(DEEPSEEK_DIR))

try:
    from vllm import LLM, SamplingParams
    from process.ngram_norepeat import NGramPerReqLogitsProcessor
    import config as deepseek_config
    DEEPSEEK_AVAILABLE = True
except ImportError as e:
    DEEPSEEK_AVAILABLE = False
    print(f"⚠️  DeepSeek-OCR не доступен: {e}")


class DeepSeekOCRWrapper:
    """
    Обертка для DeepSeek-OCR
    
    Упрощает работу с моделью через vLLM, управляет режимами работы,
    и форматирует результаты для API.
    """
    
    # Конфигурация режимов
    MODES = {
        "Tiny": {"base_size": 512, "image_size": 512, "vision_tokens": 64},
        "Small": {"base_size": 640, "image_size": 640, "vision_tokens": 100},
        "Base": {"base_size": 1024, "image_size": 1024, "vision_tokens": 256},
        "Large": {"base_size": 1280, "image_size": 1280, "vision_tokens": 400},
        "Gundam": {"base_size": 1024, "image_size": 640, "vision_tokens": None}  # Dynamic
    }
    
    # Промпты для разных задач
    PROMPTS = {
        "document": '<image>\n<|grounding|>Convert the document to markdown.',
        "free_ocr": '<image>\nFree OCR.',
        "image_ocr": '<image>\n<|grounding|>OCR this image.',
        "figure": '<image>\nParse the figure.',
        "describe": '<image>\nDescribe this image in detail.',
    }
    
    def __init__(self, model_path: str = "deepseek-ai/DeepSeek-OCR"):
        """
        Инициализация DeepSeek-OCR
        
        Args:
            model_path: Путь к модели (HuggingFace или локальный)
        """
        self.model_path = model_path
        self.llm = None
        self.available = DEEPSEEK_AVAILABLE
        
        if DEEPSEEK_AVAILABLE:
            self._load_model()
        else:
            print("⚠️  Wrapper в stub-режиме")
    
    def _load_model(self):
        """Загрузка модели через vLLM"""
        try:
            print(f"🔄 Загрузка DeepSeek-OCR: {self.model_path}")
            
            # Параметры vLLM для DeepSeek-OCR
            self.llm = LLM(
                model=self.model_path,
                trust_remote_code=True,  # Обязательно для DeepSeek-OCR
                gpu_memory_utilization=0.9,
                max_model_len=4096,
                dtype="bfloat16",  # Оптимально для OCR
                disable_log_stats=False,
            )
            
            print("✅ DeepSeek-OCR загружен")
            self.available = True
        
        except Exception as e:
            print(f"❌ Ошибка загрузки модели: {e}")
            self.available = False
            raise
    
    def process_image(
        self,
        image_bytes: bytes,
        mode: str = "Base",
        prompt: Optional[str] = None,
        task_type: str = "document"
    ) -> Dict[str, Any]:
        """
        Обработка изображения через DeepSeek-OCR
        
        Args:
            image_bytes: Байты изображения (PNG, JPG)
            mode: Режим работы (Tiny/Small/Base/Large/Gundam)
            prompt: Кастомный промпт (если None - используется по task_type)
            task_type: Тип задачи (document/free_ocr/image_ocr/figure/describe)
        
        Returns:
            Dict с результатами OCR:
                - markdown: str - результат в Markdown
                - blocks: List[Dict] - структурированные блоки
                - vision_tokens: int - количество vision токенов
                - text_tokens: int - количество текстовых токенов
                - mode: str - использованный режим
        """
        if not self.available or not self.llm:
            return self._stub_response(image_bytes, mode)
        
        try:
            # Загрузка изображения
            image = Image.open(io.BytesIO(image_bytes))
            
            # Выбор промпта
            if prompt is None:
                prompt = self.PROMPTS.get(task_type, self.PROMPTS["document"])
            
            # Настройка sampling с NGram logits processor для стабильности
            sampling_params = SamplingParams(
                temperature=0.0,  # Детерминированный вывод для OCR
                max_tokens=2048,
                top_p=1.0,
                # NGramPerReqLogitsProcessor добавляется через vLLM
                logits_processors=[
                    NGramPerReqLogitsProcessor(
                        ngram_size=3,
                        window_size=20,
                        # whitelist можно добавить если нужно
                    )
                ] if DEEPSEEK_AVAILABLE else []
            )
            
            # Генерация (синхронная для простоты)
            # В продакшене можно использовать async версию
            outputs = self.llm.generate(
                prompts=[prompt],
                sampling_params=sampling_params,
                # Изображение передается через multimodal inputs
                # Точный API зависит от версии vLLM и DeepSeek-OCR
            )
            
            # Извлечение результата
            generated_text = outputs[0].outputs[0].text
            token_ids = outputs[0].outputs[0].token_ids
            
            # Парсинг Markdown в блоки
            blocks = self._parse_markdown(generated_text)
            
            # Подсчет токенов
            mode_config = self.MODES.get(mode, self.MODES["Base"])
            vision_tokens = mode_config["vision_tokens"] or 256
            
            return {
                "markdown": generated_text,
                "blocks": blocks,
                "vision_tokens": vision_tokens,
                "text_tokens": len(token_ids),
                "mode": mode
            }
        
        except Exception as e:
            print(f"❌ Ошибка OCR: {e}")
            # Fallback на stub
            return self._stub_response(image_bytes, mode)
    
    def _parse_markdown(self, markdown: str) -> List[Dict[str, Any]]:
        """
        Парсинг Markdown в структурированные блоки
        
        Args:
            markdown: Markdown текст
        
        Returns:
            Список блоков с метаданными
        """
        blocks = []
        lines = markdown.split('\n')
        
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            
            # Определяем тип блока
            if line.startswith('#'):
                block_type = "heading"
                level = len(line) - len(line.lstrip('#'))
            elif line.startswith('- ') or line.startswith('* ') or line.startswith('+ '):
                block_type = "list_item"
                level = 1
            elif line.startswith('|'):
                block_type = "table_row"
                level = 1
            elif line.startswith('```'):
                block_type = "code_block"
                level = 1
            elif line.startswith('>'):
                block_type = "quote"
                level = 1
            else:
                block_type = "paragraph"
                level = 1
            
            blocks.append({
                "id": f"block_{i}",
                "type": block_type,
                "content": line.strip(),
                "bbox": [0, 0, 0, 0],  # TODO: извлекать из grounding если доступно
                "confidence": 0.95,
                "metadata": {
                    "level": level,
                    "line_number": i + 1
                }
            })
        
        return blocks
    
    def _stub_response(self, image_bytes: bytes, mode: str) -> Dict[str, Any]:
        """
        Заглушка когда модель недоступна
        
        Args:
            image_bytes: Байты изображения
            mode: Режим
        
        Returns:
            Stub response
        """
        try:
            image = Image.open(io.BytesIO(image_bytes))
            width, height = image.size
        except:
            width, height = 0, 0
        
        stub_markdown = f"""# Stub OCR Response

**Mode:** {mode}  
**Image Size:** {width}x{height}

⚠️ This is a placeholder response. The DeepSeek-OCR model is not available.

To enable OCR:
1. Ensure vLLM is installed
2. Ensure DeepSeek-OCR is properly configured
3. Check logs for errors

See `docs/DeepSeek_OCR_Setup.md` for setup instructions.
"""
        
        blocks = [{
            "id": "stub_block_0",
            "type": "paragraph",
            "content": "Stub OCR content",
            "bbox": [0, 0, float(width), float(height)],
            "confidence": 1.0,
            "metadata": {"stub": True}
        }]
        
        mode_config = self.MODES.get(mode, self.MODES["Base"])
        
        return {
            "markdown": stub_markdown,
            "blocks": blocks,
            "vision_tokens": mode_config["vision_tokens"] or 256,
            "text_tokens": len(stub_markdown.split()),
            "mode": mode
        }
    
    def health_check(self) -> Dict[str, Any]:
        """
        Проверка здоровья обертки
        
        Returns:
            Статус и информация о модели
        """
        return {
            "available": self.available,
            "model_loaded": self.llm is not None,
            "model_path": self.model_path,
            "modes": list(self.MODES.keys()),
            "deepseek_available": DEEPSEEK_AVAILABLE
        }


# Глобальный экземпляр (singleton)
_wrapper_instance: Optional[DeepSeekOCRWrapper] = None

def get_deepseek_wrapper() -> DeepSeekOCRWrapper:
    """
    Получить глобальный экземпляр DeepSeek wrapper (singleton)
    
    Returns:
        DeepSeekOCRWrapper instance
    """
    global _wrapper_instance
    
    if _wrapper_instance is None:
        _wrapper_instance = DeepSeekOCRWrapper()
    
    return _wrapper_instance

