#!/usr/bin/env python3
"""
Фокусированный тест: структурированные промпты для извлечения BPMN графа
БЕЗ crop_mode (чтобы избежать CUDA errors)
"""

import requests
import time

OCR_URL = "http://localhost:8000/ocr/figure"
TEST_IMAGE = "output/page_54_fresh_300dpi.png"

def test_prompt(name, prompt_config):
    print(f"\n{'='*100}")
    print(f"🧪 {name}")
    print(f"{'='*100}\n")
    
    with open(TEST_IMAGE, 'rb') as f:
        img_data = f.read()
    
    files = {"file": ("test.png", img_data, "image/png")}
    
    print(f"⚙️ Параметры:")
    for k, v in prompt_config.items():
        if k != 'custom_prompt':
            print(f"   {k}: {v}")
    
    if prompt_config.get('custom_prompt'):
        print(f"\n💬 Промпт:")
        print(f"   {prompt_config['custom_prompt'][:300]}...")
    
    try:
        start = time.time()
        response = requests.post(OCR_URL, files=files, data=prompt_config, timeout=120)
        elapsed = time.time() - start
        
        if response.status_code == 200:
            result = response.json()
            raw = result.get('raw_output', '')
            
            print(f"\n✅ Успех! Время: {elapsed:.2f} сек")
            print(f"📏 Длина: {len(raw)} символов\n")
            
            # Анализ
            has_list = '•' in raw or ('-' in raw and '\n' in raw)
            has_numbers = any(f'{i}.' in raw for i in range(1, 10))
            has_bpmn = any(kw in raw.lower() for kw in ['процесс', 'событие', 'process', 'event'])
            has_connections = any(kw in raw.lower() for kw in ['→', '->', 'связан', 'connected', 'arrow'])
            has_types = any(kw in raw.lower() for kw in ['задача', 'task', 'gateway', 'шлюз', 'решение'])
            
            print(f"📊 Анализ:")
            print(f"   Структурированность: {'✅ Списки' if has_list else '❌'}")
            print(f"   Нумерация: {'✅' if has_numbers else '❌'}")
            print(f"   BPMN элементы: {'✅' if has_bpmn else '❌'}")
            print(f"   Связи: {'✅' if has_connections else '❌'}")
            print(f"   Типы элементов: {'✅' if has_types else '❌'}")
            
            print(f"\n📄 ПОЛНЫЙ ВЫВОД:")
            print("─" * 100)
            print(raw)
            print("─" * 100)
            
            return raw
        else:
            print(f"❌ HTTP {response.status_code}: {response.text[:300]}")
            return None
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return None

def main():
    print("🔬 ФОКУСИРОВАННЫЙ ТЕСТ: Структурированные промпты для BPMN\n")
    
    # Проверка сервиса
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        print(f"✅ OCR сервис работает\n")
    except:
        print(f"❌ Сервис недоступен! Запустите его перед тестом.\n")
        return
    
    tests = [
        {
            'name': "1. Parse Figure + Русский структурированный (БЕЗ crop)",
            'config': {
                'prompt_type': 'parse_figure',
                'base_size': 1280,
                'image_size': 1280,
                'crop_mode': False,  # БЕЗ crop!
                'custom_prompt': (
                    "Разбери данную BPMN диаграмму структурированно:\n"
                    "1. Перечисли все элементы (процессы, события, шлюзы) с их названиями\n"
                    "2. Укажи тип каждого элемента (задача, решение, начало, конец)\n"
                    "3. Опиши связи между элементами (какие стрелки куда ведут)\n"
                    "4. Ответ дай в виде списка на русском языке."
                )
            }
        },
        {
            'name': "2. Parse Figure + Английский структурированный",
            'config': {
                'prompt_type': 'parse_figure',
                'base_size': 1280,
                'image_size': 1280,
                'crop_mode': False,
                'custom_prompt': (
                    "Parse this BPMN diagram in structured format:\n"
                    "1. List all elements (processes, events, gateways) with their names\n"
                    "2. Specify the type of each element (task, decision, start, end)\n"
                    "3. Describe connections between elements (which arrows lead where)\n"
                    "4. Output as structured list with clear relationships."
                )
            }
        },
        {
            'name': "3. Parse Figure + JSON формат (русский)",
            'config': {
                'prompt_type': 'parse_figure',
                'base_size': 1280,
                'image_size': 1280,
                'crop_mode': False,
                'custom_prompt': (
                    "Извлеки структуру BPMN диаграммы в JSON формате:\n"
                    "{\n"
                    '  "elements": [\n'
                    '    {"id": "1", "type": "task", "name": "Процесс 1"},\n'
                    '    ...\n'
                    '  ],\n'
                    '  "connections": [\n'
                    '    {"from": "1", "to": "2", "label": ""},\n'
                    '    ...\n'
                    '  ]\n'
                    "}"
                )
            }
        },
        {
            'name': "4. Describe + Детальный граф",
            'config': {
                'prompt_type': 'describe',
                'base_size': 1280,
                'image_size': 1280,
                'crop_mode': False,
                'custom_prompt': (
                    "Describe this BPMN diagram as a directed graph:\n"
                    "- For each node: name, shape/type, position\n"
                    "- For each edge: source node, target node, label\n"
                    "Provide complete graph structure."
                )
            }
        }
    ]
    
    results = {}
    for test in tests:
        output = test_prompt(test['name'], test['config'])
        results[test['name']] = output
        time.sleep(3)
    
    # Сохранение
    import json
    from pathlib import Path
    output_dir = Path("output/experiment_b_structured")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for name, output in results.items():
        if output:
            safe_name = name.replace('/', '_').replace(':', '').replace(' ', '_')[:50]
            with open(output_dir / f"{safe_name}.txt", 'w', encoding='utf-8') as f:
                f.write(output)
    
    print(f"\n✅ Результаты сохранены в: {output_dir}/")

if __name__ == "__main__":
    main()

