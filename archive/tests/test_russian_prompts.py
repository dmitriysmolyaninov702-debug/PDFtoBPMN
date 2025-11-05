#!/usr/bin/env python3
"""
Тест РУССКИХ промптов - Эксперимент A
Проверяем гипотезу: явное указание "Language: Russian" решит проблему транслитерации
"""

import requests
import time
import json
from pathlib import Path


def test_russian_prompts():
    """Тестирование русских промптов на BPMN диаграмме"""
    
    print("="*100)
    print("🧪 ЭКСПЕРИМЕНТ A: РУССКИЕ ПРОМПТЫ С ЯВНЫМ УКАЗАНИЕМ ЯЗЫКА")
    print("="*100)
    print("\n📋 ГИПОТЕЗА: Модель умеет работать с ~100 языками (включая русский)")
    print("   Проблема была в том, что мы НЕ указывали язык!")
    print("   Решение: добавить 'Language: Russian' в промпт\n")
    
    # Проверка сервиса
    ocr_url = "http://localhost:8000"
    try:
        health = requests.get(f"{ocr_url}/health", timeout=5)
        if health.status_code != 200:
            print(f"❌ OCR сервис не готов: HTTP {health.status_code}")
            print("\n💡 Запустите сервис:")
            print("   cd /home/budnik_an/Obligations")
            print("   source DeepSeek-OCR/venv/bin/activate")
            print("   python -m uvicorn pdf_to_context.ocr_service.app:app --host 0.0.0.0 --port 8000")
            return
    except Exception as e:
        print(f"❌ OCR сервис недоступен: {e}")
        print("\n💡 Запустите сервис первым!")
        return
    
    print("✅ OCR сервис готов\n")
    
    # Тестовое изображение
    test_image = "output/page_54_fresh_300dpi.png"
    if not Path(test_image).exists():
        print(f"❌ Тестовое изображение не найдено: {test_image}")
        return
    
    print(f"📷 Тестовое изображение: {test_image}\n")
    
    # Промпты для тестирования
    test_configs = [
        {
            "name": "🔴 BASELINE: ocr_simple (старый)",
            "prompt_type": "ocr_simple",
            "description": "Для сравнения - ожидаем npoecc1, C6bITHe1"
        },
        {
            "name": "🟢 NEW: russian_simple",
            "prompt_type": "russian_simple",
            "description": "Простейший: 'Russian. OCR with coordinates.'"
        },
        {
            "name": "🟢 NEW: russian_layout",
            "prompt_type": "russian_layout",
            "description": "Базовый: 'Language: Russian. Extract all text with coordinates.'"
        },
        {
            "name": "🟢 NEW: russian_bpmn",
            "prompt_type": "russian_bpmn",
            "description": "BPMN-специфичный: 'Language: Russian. This is a BPMN diagram...'"
        },
        {
            "name": "🟢 NEW: russian_preserve",
            "prompt_type": "russian_preserve",
            "description": "Агрессивный: 'Russian text (Cyrillic). Preserve characters exactly...'"
        },
        {
            "name": "🟢 NEW: russian_full",
            "prompt_type": "russian_full",
            "description": "Детальный: 'Language: Russian (Cyrillic). BPMN diagram...'"
        },
    ]
    
    results = []
    
    with open(test_image, 'rb') as f:
        img_data = f.read()
    
    for i, config in enumerate(test_configs, 1):
        print("="*100)
        print(f"{config['name']} ({i}/{len(test_configs)})")
        print("="*100)
        print(f"📝 {config['description']}")
        print()
        
        files = {"file": ("test.png", img_data, "image/png")}
        data = {
            "prompt_type": config['prompt_type'],
            "base_size": 1024,
            "image_size": 1024,
            "crop_mode": False
        }
        
        try:
            start = time.time()
            response = requests.post(
                f"{ocr_url}/ocr/figure",
                files=files,
                data=data,
                timeout=120
            )
            elapsed = time.time() - start
            
            if response.status_code == 200:
                result = response.json()
                raw = result.get('raw_output', '')
                blocks = result.get('blocks', [])
                
                print(f"⏱️  Время: {elapsed:.2f} сек")
                print(f"📊 Блоков: {len(blocks)}")
                print(f"🔤 Raw output: {len(raw)} символов")
                
                # КРИТИЧЕСКИЙ АНАЛИЗ: Ищем ключевые слова BPMN
                bpmn_elements = {
                    'Процесс 1': 'процесс 1' in raw.lower(),
                    'Процесс 2': 'процесс 2' in raw.lower(),
                    'Процесс 3': 'процесс 3' in raw.lower(),
                    'Событие 1': 'событие 1' in raw.lower(),
                    'Событие 2': 'событие 2' in raw.lower(),
                }
                
                # Проверка транслитерации (признак проблемы)
                has_translit = any(word in raw for word in ['npoecc', 'C6bITH', 'npo'])
                
                # Проверка координат
                has_coords = '<|det|>' in raw
                num_coords = raw.count('<|det|>')
                
                found_elements = [k for k, v in bpmn_elements.items() if v]
                
                print(f"\n🎯 КРИТИЧЕСКИЙ АНАЛИЗ:")
                print(f"   ✅ Найдено BPMN элементов: {len(found_elements)}/5")
                if found_elements:
                    print(f"      {', '.join(found_elements)}")
                print(f"   {'❌' if has_translit else '✅'} Транслитерация: {'ЕСТЬ (плохо!)' if has_translit else 'НЕТ (хорошо!)'}")
                print(f"   {'✅' if has_coords else '❌'} Координаты: {'Есть' if has_coords else 'Нет'} ({num_coords} шт.)")
                
                # Показываем примеры из raw output
                if has_translit:
                    print(f"\n⚠️  ТРАНСЛИТЕРАЦИЯ ОБНАРУЖЕНА:")
                    for word in ['npoecc', 'C6bITH', 'npo']:
                        if word in raw:
                            idx = raw.find(word)
                            snippet = raw[max(0, idx-20):min(len(raw), idx+60)]
                            print(f"      ...{snippet}...")
                            break
                
                if found_elements:
                    print(f"\n✅ ПРАВИЛЬНАЯ КИРИЛЛИЦА:")
                    for elem in found_elements[:2]:  # Показываем первые 2
                        elem_lower = elem.lower()
                        idx = raw.lower().find(elem_lower)
                        if idx >= 0:
                            snippet = raw[max(0, idx-20):min(len(raw), idx+len(elem)+20)]
                            print(f"      ...{snippet}...")
                
                # Показываем блоки если есть
                if blocks:
                    print(f"\n🧩 ПРИМЕРЫ БЛОКОВ:")
                    for j, block in enumerate(blocks[:3], 1):
                        text = block.get('text', block.get('content', ''))
                        bbox = block.get('bbox', {})
                        print(f"   Блок {j}: {text[:60]}")
                        if bbox:
                            print(f"           bbox: {bbox}")
                
                # Сохраняем результат
                results.append({
                    'name': config['name'],
                    'prompt_type': config['prompt_type'],
                    'elapsed': elapsed,
                    'blocks': len(blocks),
                    'found_elements': found_elements,
                    'has_translit': has_translit,
                    'has_coords': has_coords,
                    'success': len(found_elements) >= 3 and not has_translit and has_coords
                })
                
            else:
                print(f"❌ HTTP {response.status_code}")
                results.append({
                    'name': config['name'],
                    'error': response.status_code
                })
        
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            results.append({
                'name': config['name'],
                'error': str(e)
            })
        
        print()
        time.sleep(2)
    
    # Итоговая таблица
    print("\n" + "="*100)
    print("📊 ИТОГОВАЯ ТАБЛИЦА РЕЗУЛЬТАТОВ")
    print("="*100)
    print(f"{'Промпт':<40} {'Время':<10} {'BPMN элементов':<15} {'Транслит':<12} {'Координаты':<12} {'УСПЕХ':<10}")
    print("-"*100)
    
    for r in results:
        if 'error' in r:
            print(f"{r['name']:<40} {'ERROR':<10}")
        else:
            translit = '❌ ДА' if r['has_translit'] else '✅ НЕТ'
            coords = '✅ ДА' if r['has_coords'] else '❌ НЕТ'
            success = '🎉 ДА' if r['success'] else '❌ НЕТ'
            found = len(r['found_elements'])
            print(f"{r['name']:<40} {r['elapsed']:>8.2f}  {found:>13}/5  {translit:<12} {coords:<12} {success:<10}")
    
    # Финальные выводы
    print("\n" + "="*100)
    print("🎯 ВЫВОДЫ ЭКСПЕРИМЕНТА A")
    print("="*100)
    
    successful = [r for r in results if r.get('success', False)]
    
    if successful:
        print(f"\n🎉 ПРОРЫВ! Успешных промптов: {len(successful)}")
        print(f"\n✅ РАБОТАЮЩИЕ ПРОМПТЫ:")
        for r in successful:
            print(f"   - {r['prompt_type']}: {len(r['found_elements'])}/5 элементов, без транслита, с координатами")
        
        best = max(successful, key=lambda x: len(x['found_elements']))
        print(f"\n🏆 ЛУЧШИЙ ПРОМПТ: {best['prompt_type']}")
        print(f"   Найдено: {len(best['found_elements'])}/5 элементов")
        print(f"   Время: {best['elapsed']:.2f} сек")
        print(f"\n💡 РЕКОМЕНДАЦИЯ: Использовать '{best['prompt_type']}' для русских BPMN диаграмм")
    else:
        print(f"\n❌ ГИПОТЕЗА НЕ ПОДТВЕРДИЛАСЬ")
        print(f"   Ни один промпт не дал правильный результат")
        print(f"\n💡 СЛЕДУЮЩИЙ ШАГ: Вариант B (комбинированный подход)")
    
    # Сохранение результатов
    output_file = "output/russian_prompts_experiment_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'test_image': test_image,
            'results': results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n📁 Результаты сохранены: {output_file}")
    print("="*100)


if __name__ == "__main__":
    try:
        test_russian_prompts()
    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")
    except Exception as e:
        print(f"\n\n❌ Неожиданная ошибка: {e}")
        import traceback
        traceback.print_exc()

