#!/usr/bin/env python3
"""
Повторный тест страницы 23 документа ДП-М1.020-06 с промптом ocr_simple

Страница 23 содержит BPMN диаграмму "Процесс мониторинга состояния аэродромной инфраструктуры"
Промпт ocr_simple показал лучшие результаты: 55+ элементов с координатами
"""

import os
import sys
import time
import json
import requests
from pathlib import Path

# Добавляем путь к модулю pdf_to_context
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

# Настройки
OCR_URL = "http://localhost:8000/ocr/figure"
HEALTH_URL = "http://localhost:8000/health"
IMAGE_PATH = "/home/budnik_an/Obligations/archive/old_docs/debug_images/page_23_image_1.png"
OUTPUT_DIR = "/home/budnik_an/Obligations/output/page_23_test"


def check_ocr_service():
    """Проверить доступность OCR сервиса"""
    try:
        response = requests.get(HEALTH_URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get("status") == "healthy"
    except:
        pass
    return False


def render_page_23():
    """Рендерим страницу 23 из PDF (если изображение не существует)"""
    if os.path.exists(IMAGE_PATH):
        print(f"✅ Изображение уже существует: {IMAGE_PATH}")
        return IMAGE_PATH
    
    print("📄 Рендерим страницу 23 из PDF...")
    import fitz  # PyMuPDF
    
    pdf_path = "/home/budnik_an/Obligations/input/ДП-М1.020-06 (Эталон №14 для ознакомления).pdf"
    doc = fitz.open(pdf_path)
    page = doc[22]  # Страница 23 (индекс 22)
    
    # Рендерим в высоком разрешении (300 DPI)
    mat = fitz.Matrix(300/72, 300/72)
    pix = page.get_pixmap(matrix=mat)
    
    # Сохраняем
    os.makedirs(os.path.dirname(IMAGE_PATH), exist_ok=True)
    pix.save(IMAGE_PATH)
    
    print(f"✅ Изображение сохранено: {IMAGE_PATH}")
    print(f"   Размер: {pix.width}x{pix.height} пикселей")
    
    doc.close()
    return IMAGE_PATH


def test_ocr_simple(image_path: str):
    """
    Тестировать ocr_simple промпт на странице 23
    
    Args:
        image_path: Путь к изображению страницы 23
    
    Returns:
        dict: Результаты теста
    """
    print(f"\n{'='*80}")
    print(f"🧪 ТЕСТИРУЕМ: ocr_simple промпт на странице 23")
    print(f"{'='*80}")
    
    if not os.path.exists(image_path):
        print(f"❌ Изображение не найдено: {image_path}")
        return None
    
    print(f"📷 Изображение: {image_path}")
    print(f"🎯 Промпт: ocr_simple")
    print(f"🔍 Ожидаем: 55+ элементов BPMN с координатами")
    
    # Отправляем запрос
    start_time = time.time()
    
    with open(image_path, 'rb') as f:
        files = {'file': ('page_23.png', f, 'image/png')}
        data = {'prompt_type': 'ocr_simple'}
        
        print(f"\n⏳ Отправляем запрос в OCR сервис...")
        
        try:
            response = requests.post(OCR_URL, files=files, data=data, timeout=120)
            elapsed = time.time() - start_time
            
            if response.status_code != 200:
                print(f"❌ Ошибка HTTP {response.status_code}")
                print(f"   {response.text[:500]}")
                return None
            
            result = response.json()
            
            # Извлекаем данные
            blocks = result.get('blocks', [])
            markdown = result.get('markdown', '')
            raw_output = result.get('raw_output', '')
            
            # Статистика
            print(f"\n{'='*80}")
            print(f"📊 РЕЗУЛЬТАТЫ")
            print(f"{'='*80}")
            print(f"⏱️  Время обработки: {elapsed:.2f} сек")
            print(f"📦 Блоков распознано: {len(blocks)}")
            print(f"📝 Длина markdown: {len(markdown):,} символов")
            print(f"🔤 Длина raw output: {len(raw_output):,} символов")
            
            # Подсчет элементов с координатами
            coord_count = raw_output.count('<|ref|>') if raw_output else 0
            print(f"📍 Элементов с координатами: {coord_count}")
            
            # Показываем первые 1000 символов markdown
            if markdown:
                print(f"\n{'='*80}")
                print(f"📝 MARKDOWN (первые 1000 символов):")
                print(f"{'='*80}")
                print(markdown[:1000])
                if len(markdown) > 1000:
                    print("...")
                    print(f"\n... (всего {len(markdown):,} символов)")
            
            # Показываем первые 1500 символов raw output
            if raw_output:
                print(f"\n{'='*80}")
                print(f"🔍 RAW OUTPUT (первые 1500 символов):")
                print(f"{'='*80}")
                print(raw_output[:1500])
                if len(raw_output) > 1500:
                    print("...")
                    print(f"\n... (всего {len(raw_output):,} символов)")
            
            # Парсим элементы с координатами
            if '<|ref|>' in raw_output:
                print(f"\n{'='*80}")
                print(f"📍 РАСПОЗНАННЫЕ ЭЛЕМЕНТЫ BPMN (первые 10):")
                print(f"{'='*80}")
                
                import re
                pattern = r'<\|ref\|>(.*?)<\|/ref\|><\|det\|>\[\[(.*?)\]\]<\|/det\|>'
                matches = re.findall(pattern, raw_output)
                
                for i, (text, coords) in enumerate(matches[:10], 1):
                    print(f"{i:2}. Текст: {text[:60]}")
                    print(f"    Координаты: {coords}")
                
                if len(matches) > 10:
                    print(f"\n... и еще {len(matches) - 10} элементов")
                
                print(f"\n💯 ИТОГО: {len(matches)} элементов BPMN извлечено с координатами!")
            
            # Сохраняем результаты
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            
            # Сохраняем JSON
            output_json = Path(OUTPUT_DIR) / "page_23_ocr_simple_result.json"
            with open(output_json, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\n💾 Результаты сохранены: {output_json}")
            
            # Сохраняем markdown
            output_md = Path(OUTPUT_DIR) / "page_23_ocr_simple_result.md"
            with open(output_md, 'w', encoding='utf-8') as f:
                f.write(f"# Результаты OCR страницы 23 (промпт: ocr_simple)\n\n")
                f.write(f"**Время:** {elapsed:.2f} сек\n")
                f.write(f"**Элементов:** {coord_count}\n\n")
                f.write(f"## Raw Output\n\n```\n{raw_output}\n```\n\n")
                f.write(f"## Markdown\n\n{markdown}\n")
            print(f"💾 Markdown сохранен: {output_md}")
            
            return {
                'success': True,
                'elapsed': elapsed,
                'blocks': len(blocks),
                'markdown_length': len(markdown),
                'raw_output_length': len(raw_output),
                'elements_with_coords': coord_count
            }
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return None


def main():
    """Главная функция"""
    print("\n" + "="*80)
    print("🧪 ПОВТОРНЫЙ ТЕСТ СТРАНИЦЫ 23 с промптом ocr_simple")
    print("="*80)
    print()
    print("📄 Документ: ДП-М1.020-06")
    print("📃 Страница: 23 (BPMN диаграмма)")
    print("🎯 Промпт: ocr_simple")
    print("💡 Предыдущий результат: 55+ элементов с координатами")
    print()
    
    # Проверяем OCR сервис
    if not check_ocr_service():
        print("❌ OCR сервис недоступен!")
        print()
        print("🚀 Запустите сервис в отдельном терминале:")
        print()
        print("   cd ~/Obligations")
        print("   source DeepSeek-OCR/venv/bin/activate")
        print("   python -m uvicorn pdf_to_context.ocr_service.app:app --host 0.0.0.0 --port 8000")
        print()
        sys.exit(1)
    
    print("✅ OCR сервис доступен")
    
    # Проверяем наличие изображения
    image_path = render_page_23()
    
    # Запускаем тест
    result = test_ocr_simple(image_path)
    
    if result and result['success']:
        print(f"\n{'='*80}")
        print(f"✅ ТЕСТ УСПЕШНО ЗАВЕРШЕН!")
        print(f"{'='*80}")
        print(f"⏱️  Время: {result['elapsed']:.2f} сек")
        print(f"📍 Элементов с координатами: {result['elements_with_coords']}")
        print(f"📝 Markdown: {result['markdown_length']:,} символов")
        print(f"🔤 Raw output: {result['raw_output_length']:,} символов")
        print()
        print(f"📁 Результаты сохранены в: {OUTPUT_DIR}")
        print()
        print("💡 ВЫВОД:")
        if result['elements_with_coords'] >= 50:
            print("   ✅ ocr_simple отлично подходит для BPMN диаграмм!")
            print("   ✅ Извлечены элементы с точными координатами")
            print("   ✅ Можно использовать для построения графа процесса")
        else:
            print("   ⚠️  Результат хуже ожидаемого, проверьте настройки OCR")
    else:
        print(f"\n❌ Тест завершился с ошибкой")
        sys.exit(1)


if __name__ == "__main__":
    main()

