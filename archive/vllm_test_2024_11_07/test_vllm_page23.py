#!/usr/bin/env python3
"""
Тестирование vLLM 0.11.0 на странице 23 документа ДП-М1.020-06
Сравнение с результатами Transformers+flash_attn
"""

import os
import sys
import time
import torch
from pathlib import Path

# Настройки окружения для vLLM
os.environ["CUDA_VISIBLE_DEVICES"] = '0'

from vllm import LLM, SamplingParams
from PIL import Image, ImageOps

# Используем встроенный в vLLM 0.11.0 логит процессор для DeepSeek-OCR
NGramPerReqLogitsProcessor = None
try:
    from vllm.model_executor.models.deepseek_ocr import NGramPerReqLogitsProcessor
    print("✅ Используется встроенный NGramPerReqLogitsProcessor из vLLM 0.11.0")
except ImportError:
    print("⚠️ NGramPerReqLogitsProcessor не найден - пропускаем")


def load_image(image_path):
    """Загрузить изображение с коррекцией EXIF"""
    try:
        image = Image.open(image_path)
        corrected_image = ImageOps.exif_transpose(image)
        return corrected_image
    except Exception as e:
        print(f"⚠️ Ошибка загрузки изображения: {e}")
        return Image.open(image_path)


def generate_with_vllm(llm, image, prompt):
    """Генерация с использованием vLLM 0.11.0"""
    
    # Параметры семплирования
    sampling_kwargs = {
        "temperature": 0.0,
        "max_tokens": 8192,
        "skip_special_tokens": False,
    }
    
    # Добавляем параметры для NGram логит процессора если доступен
    if NGramPerReqLogitsProcessor is not None:
        sampling_kwargs["extra_args"] = dict(
            ngram_size=30,
            window_size=90,
            whitelist_token_ids={128821, 128822},  # <td>, </td>
        )
    
    sampling_params = SamplingParams(**sampling_kwargs)
    
    # Формируем запрос (vLLM 0.11.0 API)
    model_input = {
        "prompt": prompt,
        "multi_modal_data": {"image": image}
    }
    
    print(f"\n{'='*80}")
    print(f"🔄 ГЕНЕРАЦИЯ (vLLM 0.11.0)")
    print(f"{'='*80}\n")
    
    start_time = time.time()
    
    # Генерация (синхронный API)
    outputs = llm.generate([model_input], sampling_params)
    
    elapsed_time = time.time() - start_time
    
    # Извлекаем результат
    result = outputs[0].outputs[0].text
    
    print(result)
    print(f"\n\n⏱️ Время генерации: {elapsed_time:.2f} сек")
    
    return result


def main():
    """Основная функция тестирования"""
    
    print(f"\n{'='*80}")
    print(f"🧪 ТЕСТИРОВАНИЕ vLLM 0.11.0 НА СТРАНИЦЕ 23")
    print(f"{'='*80}\n")
    
    # Пути
    image_path = Path("/home/budnik_an/Obligations/output/vllm_test/page_23.png")
    output_dir = Path("/home/budnik_an/Obligations/output/vllm_test")
    output_file = output_dir / "vllm_0.11_result.txt"
    
    # Проверка изображения
    if not image_path.exists():
        print(f"❌ Изображение не найдено: {image_path}")
        return
    
    print(f"✅ Изображение: {image_path}")
    print(f"   Размер файла: {image_path.stat().st_size / 1024:.1f} KB")
    
    # Загрузка изображения
    print("\n📥 Загружаем изображение...")
    image = load_image(str(image_path)).convert('RGB')
    print(f"✅ Размер: {image.size[0]}x{image.size[1]} пикселей")
    
    # Промпт ocr_simple (лучший результат на тестах)
    prompt = '<image>\n<|grounding|>OCR this image.'
    print(f"\n📝 Промпт: ocr_simple")
    print(f"   '{prompt}'")
    
    # Инициализация vLLM 0.11.0
    print("\n📦 Инициализация vLLM 0.11.0...")
    print("   (Может занять 1-2 минуты при первом запуске)")
    
    # Подготовка параметров модели
    llm_kwargs = {
        "model": "deepseek-ai/DeepSeek-OCR",
        "trust_remote_code": True,
        "enable_prefix_caching": False,
        "mm_processor_cache_gb": 0,
        "gpu_memory_utilization": 0.75,
        "max_model_len": 8192,
    }
    
    # Добавляем логит процессор если доступен
    if NGramPerReqLogitsProcessor is not None:
        llm_kwargs["logits_processors"] = [NGramPerReqLogitsProcessor]
        print("   ✅ NGram логит процессор активирован")
    
    llm = LLM(**llm_kwargs)
    
    print("✅ vLLM движок готов\n")
    
    # Генерация с vLLM
    result = generate_with_vllm(llm, image, prompt)
    
    # Сохранение результата
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(result)
    
    print(f"\n{'='*80}")
    print(f"✅ РЕЗУЛЬТАТ СОХРАНЕН: {output_file}")
    print(f"{'='*80}\n")
    
    # Статистика
    lines = result.split('\n')
    print(f"📊 Статистика:")
    print(f"   Строк: {len(lines)}")
    print(f"   Символов: {len(result)}")
    print(f"   Размер файла: {output_file.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Прервано пользователем")
    except Exception as e:
        print(f"\n\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()

