#!/usr/bin/env python3
"""
Утилита для тестирования облачного DeepSeek-OCR API
https://www.deepseek-ocr.ai/docs
"""

import os
import sys
import time
import json
import requests
from pathlib import Path
from typing import Optional, Dict, Any


class CloudDeepSeekOCR:
    """Клиент для облачного DeepSeek-OCR API"""
    
    BASE_URL = "https://api.deepsee-ocr.ai"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('DEEPSEEK_OCR_API_KEY')
        if not self.api_key:
            raise ValueError(
                "API key not found. Set DEEPSEEK_OCR_API_KEY environment variable "
                "or pass api_key parameter"
            )
        
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_key}',
            'Accept': 'application/json',
        })
    
    def ocr(
        self, 
        file_path: str, 
        prompt: Optional[str] = None,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Выполнить OCR на файле
        
        Args:
            file_path: Путь к файлу (PDF или изображение)
            prompt: Инструкция для извлечения (опционально)
            language: ISO код языка (опционально)
        
        Returns:
            Словарь с результатом OCR
        """
        url = f"{self.BASE_URL}/v1/ocr"
        
        with open(file_path, 'rb') as f:
            files = {'file': (Path(file_path).name, f, self._get_mime_type(file_path))}
            data = {}
            
            if prompt:
                data['prompt'] = prompt
            if language:
                data['language'] = language
            
            try:
                response = self.session.post(url, files=files, data=data, timeout=120)
                response.raise_for_status()
                return response.json()
            
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    retry_after = e.response.json().get('retry_after', 15)
                    print(f"⚠️  Rate limit exceeded. Retry after {retry_after}s")
                    return {'error': 'rate_limit', 'retry_after': retry_after}
                elif e.response.status_code == 401:
                    print(f"❌ Unauthorized. Check your API key.")
                    return {'error': 'unauthorized'}
                else:
                    print(f"❌ HTTP Error {e.response.status_code}: {e.response.text}")
                    return {'error': f'http_{e.response.status_code}'}
            
            except Exception as e:
                print(f"❌ Error: {e}")
                return {'error': str(e)}
    
    def _get_mime_type(self, file_path: str) -> str:
        """Определить MIME тип файла"""
        ext = Path(file_path).suffix.lower()
        mime_types = {
            '.pdf': 'application/pdf',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
        }
        return mime_types.get(ext, 'application/octet-stream')


def test_cloud_ocr():
    """Тестирование облачного DeepSeek-OCR с разными промптами"""
    
    print("="*100)
    print("🌐 ТЕСТИРОВАНИЕ ОБЛАЧНОГО DeepSeek-OCR API")
    print("="*100)
    
    # Проверка API ключа
    api_key = os.environ.get('DEEPSEEK_OCR_API_KEY')
    if not api_key:
        print("\n❌ API ключ не найден!")
        print("\nУстановите переменную окружения:")
        print("  export DEEPSEEK_OCR_API_KEY='your_api_key_here'")
        print("\nИли получите API ключ:")
        print("  https://www.deepseek-ocr.ai/docs")
        return
    
    print(f"\n✅ API ключ найден: {api_key[:8]}...{api_key[-4:]}")
    
    # Инициализация клиента
    try:
        client = CloudDeepSeekOCR(api_key)
    except Exception as e:
        print(f"❌ Ошибка инициализации: {e}")
        return
    
    # Тестовое изображение
    test_image = "output/page_54_fresh_300dpi.png"
    
    if not Path(test_image).exists():
        print(f"\n❌ Тестовое изображение не найдено: {test_image}")
        return
    
    print(f"\n📷 Тестовое изображение: {test_image}")
    
    # Промпты для тестирования
    test_prompts = [
        {
            "name": "Без промпта",
            "prompt": None,
            "language": "ru"
        },
        {
            "name": "Extract all text",
            "prompt": "Extract all text from this image",
            "language": "ru"
        },
        {
            "name": "Extract BPMN elements",
            "prompt": "Extract all BPMN diagram elements including text inside shapes, boxes, and circles",
            "language": "ru"
        },
        {
            "name": "На русском с координатами",
            "prompt": "Распознай весь текст на изображении включая текст внутри фигур диаграммы. Укажи координаты элементов.",
            "language": "ru"
        },
        {
            "name": "Describe BPMN на русском",
            "prompt": "Опиши все элементы BPMN диаграммы на русском языке: названия процессов, событий, их расположение и связи",
            "language": "ru"
        },
        {
            "name": "Structured extraction",
            "prompt": "Extract text as structured data. For each element provide: name, type, and location",
            "language": "ru"
        },
    ]
    
    results = []
    
    for i, test in enumerate(test_prompts, 1):
        print(f"\n{'='*100}")
        print(f"🧪 ТЕСТ {i}/{len(test_prompts)}: {test['name']}")
        print("="*100)
        
        if test['prompt']:
            print(f"💬 Промпт: {test['prompt'][:80]}...")
        else:
            print(f"💬 Промпт: БЕЗ ПРОМПТА")
        
        print(f"🌍 Язык: {test['language']}")
        print()
        
        # Выполнение OCR
        start = time.time()
        result = client.ocr(
            test_image, 
            prompt=test['prompt'],
            language=test['language']
        )
        elapsed = time.time() - start
        
        if 'error' in result:
            print(f"❌ Ошибка: {result['error']}")
            if result['error'] == 'rate_limit':
                retry_after = result.get('retry_after', 15)
                print(f"⏳ Ожидание {retry_after} секунд...")
                time.sleep(retry_after)
                continue
            results.append({
                'name': test['name'],
                'error': result['error'],
                'elapsed': elapsed
            })
            continue
        
        # Анализ результата
        text = result.get('text', '')
        
        print(f"⏱️  Время: {elapsed:.2f} сек")
        print(f"📝 Длина текста: {len(text)} символов")
        
        # Анализ содержимого
        bpmn_keywords = ['процесс 1', 'процесс 2', 'процесс 3', 'событие 1', 'событие 2']
        found_keywords = [kw for kw in bpmn_keywords if kw in text.lower()]
        
        has_coords = any(word in text.lower() for word in ['координат', 'расположен', 'x:', 'y:', 'bbox'])
        is_russian = sum(1 for c in text if 'а' <= c.lower() <= 'я') > len(text) * 0.3
        
        print(f"\n🔍 АНАЛИЗ:")
        print(f"   Русский язык: {'✅' if is_russian else '❌'}")
        print(f"   Упоминание координат: {'✅' if has_coords else '❌'}")
        print(f"   Найдены BPMN элементы: {', '.join(found_keywords) if found_keywords else '❌'}")
        
        # Показываем результат
        print(f"\n📄 РЕЗУЛЬТАТ OCR:")
        print("-"*100)
        if len(text) > 1000:
            print(text[:1000])
            print(f"\n... (еще {len(text) - 1000} символов)")
        else:
            print(text)
        print("-"*100)
        
        # Сохраняем результат
        results.append({
            'name': test['name'],
            'elapsed': elapsed,
            'text_length': len(text),
            'bpmn_elements': found_keywords,
            'has_coords': has_coords,
            'is_russian': is_russian,
        })
        
        # Пауза между запросами
        time.sleep(2)
    
    # Итоговая таблица
    print("\n\n" + "="*100)
    print("📊 ИТОГОВАЯ ТАБЛИЦА")
    print("="*100)
    print(f"{'Тест':<40} {'Время, с':<10} {'Длина':<10} {'BPMN':<10} {'Координаты':<12} {'Русский':<10}")
    print("-"*100)
    
    for r in results:
        if 'error' in r:
            print(f"{r['name']:<40} {r['elapsed']:>8.2f}  {'ERROR':<10}")
        else:
            bpmn_count = len(r.get('bpmn_elements', []))
            coords = '✅' if r.get('has_coords') else '❌'
            russian = '✅' if r.get('is_russian') else '❌'
            print(f"{r['name']:<40} {r['elapsed']:>8.2f}  {r['text_length']:>8}  {bpmn_count:>8}  {coords:<12} {russian:<10}")
    
    print("\n" + "="*100)
    print("✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("="*100)
    
    # Сохранение результатов в JSON
    output_file = "output/cloud_deepseek_ocr_test_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'test_image': test_image,
            'results': results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n📁 Результаты сохранены: {output_file}")


def main():
    """Главная функция"""
    try:
        test_cloud_ocr()
    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Неожиданная ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

