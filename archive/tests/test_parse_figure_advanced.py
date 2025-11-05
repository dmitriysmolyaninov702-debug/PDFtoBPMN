#!/usr/bin/env python3
"""
Тестирование улучшенных режимов DeepSeek-OCR для BPMN извлечения

На основе исследования: критические параметры, которые мы НЕ использовали:
- Large mode (1280x1280) для мелких деталей
- Gundam mode (crop_mode + фрагментация)
- Структурированные промпты на русском
- <|grounding|> токен для координат
"""

import requests
import time
import json
from pathlib import Path

# Конфигурация
OCR_URL = "http://localhost:8000/ocr/figure"
HEALTH_URL = "http://localhost:8000/health"
TEST_IMAGE = "output/page_54_fresh_300dpi.png"

# Цветовые коды для вывода
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*100}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'='*100}{Colors.END}\n")

def print_test(name, description):
    print(f"{Colors.BOLD}{Colors.CYAN}🧪 ТЕСТ: {name}{Colors.END}")
    print(f"{Colors.BLUE}   {description}{Colors.END}\n")

def check_service():
    """Проверка доступности OCR сервиса"""
    try:
        response = requests.get(HEALTH_URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"{Colors.GREEN}✅ OCR сервис работает{Colors.END}")
            print(f"   GPU: {data.get('cuda_device', 'N/A')}")
            print(f"   Модель загружена: {data.get('model_loaded', False)}")
            return True
    except Exception as e:
        print(f"{Colors.RED}❌ OCR сервис недоступен: {e}{Colors.END}")
        print(f"{Colors.YELLOW}   Запустите: python -m uvicorn pdf_to_context.ocr_service.app:app --host 0.0.0.0 --port 8000{Colors.END}")
        return False

def analyze_result(raw_output: str, test_name: str):
    """Анализ результата OCR"""
    # Длина
    length = len(raw_output)
    
    # Анализ языка
    cyrillic_count = sum(1 for c in raw_output if 'а' <= c.lower() <= 'я')
    latin_count = sum(1 for c in raw_output if 'a' <= c.lower() <= 'z')
    
    if cyrillic_count > latin_count:
        language = f"{Colors.GREEN}🇷🇺 РУССКИЙ{Colors.END}"
    elif latin_count > cyrillic_count:
        language = f"{Colors.YELLOW}🇬🇧 АНГЛИЙСКИЙ{Colors.END}"
    else:
        language = "⚪ НЕОПРЕДЕЛЕН"
    
    # Поиск BPMN элементов
    bpmn_keywords = {
        'процесс 1': 0, 'процесс 2': 0, 'процесс 3': 0,
        'событие 1': 0, 'событие 2': 0,
        'process 1': 0, 'process 2': 0, 'process 3': 0,
        'event 1': 0, 'event 2': 0,
        'задача': 0, 'task': 0,
        'решение': 0, 'decision': 0, 'gateway': 0,
        'start': 0, 'end': 0, 'старт': 0, 'конец': 0
    }
    
    for keyword in bpmn_keywords:
        bpmn_keywords[keyword] = raw_output.lower().count(keyword)
    
    found_elements = {k: v for k, v in bpmn_keywords.items() if v > 0}
    
    # Поиск связей (стрелки, переходы)
    connection_keywords = ['→', '->', 'связан', 'ведёт', 'переход', 'arrow', 'connected', 'flow']
    connections_count = sum(raw_output.lower().count(kw) for kw in connection_keywords)
    
    # Поиск координат
    has_coordinates = '<|det|>' in raw_output or 'bbox' in raw_output.lower() or '[[' in raw_output
    coord_count = raw_output.count('<|det|>')
    
    # Поиск структурированного формата
    has_list = raw_output.count('•') + raw_output.count('-') + raw_output.count('*')
    has_numbering = bool(sum(raw_output.count(f'{i}.') for i in range(1, 10)))
    
    # Вывод анализа
    print(f"\n{Colors.BOLD}📊 АНАЛИЗ РЕЗУЛЬТАТА:{Colors.END}")
    print(f"   Длина: {length} символов")
    print(f"   Язык: {language}")
    print(f"   Кириллица: {cyrillic_count} | Латиница: {latin_count}")
    
    if found_elements:
        print(f"\n   {Colors.GREEN}✅ BPMN элементы найдены: {len(found_elements)}{Colors.END}")
        for elem, count in sorted(found_elements.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"      • {elem}: {count} упоминаний")
    else:
        print(f"\n   {Colors.RED}❌ BPMN элементы НЕ найдены{Colors.END}")
    
    if connections_count > 0:
        print(f"\n   {Colors.GREEN}✅ Связи найдены: {connections_count} упоминаний{Colors.END}")
    else:
        print(f"\n   {Colors.YELLOW}⚠️ Связи НЕ найдены{Colors.END}")
    
    if has_coordinates:
        print(f"\n   {Colors.GREEN}✅ Координаты присутствуют: {coord_count} блоков{Colors.END}")
    else:
        print(f"\n   {Colors.YELLOW}⚠️ Координаты отсутствуют{Colors.END}")
    
    if has_list or has_numbering:
        print(f"\n   {Colors.GREEN}✅ Структурированный формат (списки/нумерация){Colors.END}")
    else:
        print(f"\n   {Colors.YELLOW}⚠️ Неструктурированный текст{Colors.END}")
    
    # Оценка качества
    score = 0
    if found_elements: score += 40
    if connections_count > 0: score += 30
    if has_coordinates: score += 20
    if has_list or has_numbering: score += 10
    
    if score >= 80:
        quality = f"{Colors.GREEN}🎯 ОТЛИЧНО{Colors.END}"
    elif score >= 60:
        quality = f"{Colors.YELLOW}⚠️ ХОРОШО{Colors.END}"
    elif score >= 40:
        quality = f"{Colors.YELLOW}⚠️ СРЕДНЕ{Colors.END}"
    else:
        quality = f"{Colors.RED}❌ ПЛОХО{Colors.END}"
    
    print(f"\n   Общая оценка: {quality} ({score}/100)")
    
    return {
        'test_name': test_name,
        'length': length,
        'language': 'russian' if cyrillic_count > latin_count else 'english',
        'bpmn_elements_found': len(found_elements),
        'connections_found': connections_count,
        'has_coordinates': has_coordinates,
        'coordinate_blocks': coord_count,
        'structured': has_list or has_numbering,
        'quality_score': score
    }

def run_ocr_test(test_config: dict, img_data: bytes):
    """Выполнение одного теста OCR"""
    print_test(test_config['name'], test_config['description'])
    
    # Подготовка данных запроса
    files = {"file": ("test.png", img_data, "image/png")}
    data = {
        "prompt_type": test_config.get('prompt_type', 'default'),
        "base_size": test_config.get('base_size', 1024),
        "image_size": test_config.get('image_size', 1024),
        "crop_mode": test_config.get('crop_mode', False)
    }
    
    if test_config.get('custom_prompt'):
        data['custom_prompt'] = test_config['custom_prompt']
        print(f"{Colors.CYAN}💬 Кастомный промпт:{Colors.END}")
        print(f"{Colors.BLUE}   {test_config['custom_prompt'][:200]}...{Colors.END}\n")
    
    print(f"{Colors.CYAN}⚙️ Параметры:{Colors.END}")
    print(f"   prompt_type: {data['prompt_type']}")
    print(f"   base_size: {data['base_size']}, image_size: {data['image_size']}")
    print(f"   crop_mode: {data['crop_mode']}")
    
    # Выполнение запроса
    try:
        start = time.time()
        response = requests.post(OCR_URL, files=files, data=data, timeout=120)
        elapsed = time.time() - start
        
        if response.status_code == 200:
            result = response.json()
            raw_output = result.get('raw_output', '')
            
            print(f"\n{Colors.GREEN}✅ Запрос успешен{Colors.END}")
            print(f"⏱️  Время: {elapsed:.2f} сек")
            
            # Анализ результата
            analysis = analyze_result(raw_output, test_config['name'])
            analysis['time_seconds'] = elapsed
            
            # Показываем начало вывода
            print(f"\n{Colors.BOLD}📄 НАЧАЛО ВЫВОДА (800 символов):{Colors.END}")
            print(f"{Colors.BLUE}{'-'*100}{Colors.END}")
            print(raw_output[:800])
            print(f"{Colors.BLUE}{'-'*100}{Colors.END}")
            
            if len(raw_output) > 800:
                print(f"\n... (еще {len(raw_output)-800} символов)")
            
            return analysis, raw_output
        else:
            print(f"{Colors.RED}❌ HTTP {response.status_code}: {response.text[:200]}{Colors.END}")
            return None, None
    
    except Exception as e:
        print(f"{Colors.RED}❌ Ошибка: {e}{Colors.END}")
        return None, None

def main():
    print_header("🔬 ЭКСПЕРИМЕНТ B: Улучшенные режимы DeepSeek-OCR для BPMN")
    
    print(f"{Colors.BOLD}На основе исследования DeepSeek-OCR{Colors.END}")
    print(f"Тестовое изображение: {Colors.CYAN}{TEST_IMAGE}{Colors.END}\n")
    
    # Проверка сервиса
    if not check_service():
        return
    
    # Загрузка изображения
    try:
        with open(TEST_IMAGE, 'rb') as f:
            img_data = f.read()
        print(f"{Colors.GREEN}✅ Изображение загружено: {len(img_data)} байт{Colors.END}\n")
    except Exception as e:
        print(f"{Colors.RED}❌ Ошибка загрузки изображения: {e}{Colors.END}")
        return
    
    # Конфигурация тестов
    tests = [
        {
            'name': "1️⃣ Parse Figure - BASE (как было)",
            'description': "Baseline: parse_figure с базовыми параметрами (1024x1024)",
            'prompt_type': 'parse_figure',
            'base_size': 1024,
            'image_size': 1024,
            'crop_mode': False,
            'custom_prompt': None
        },
        {
            'name': "2️⃣ Parse Figure - LARGE MODE 🔥",
            'description': "НОВОЕ: 1280x1280 (400 vision tokens) для мелких деталей",
            'prompt_type': 'parse_figure',
            'base_size': 1280,
            'image_size': 1280,
            'crop_mode': False,
            'custom_prompt': None
        },
        {
            'name': "3️⃣ Parse Figure - LARGE + CROP 🔥🔥",
            'description': "НОВОЕ: Large mode + автообрезка для фокуса на диаграмме",
            'prompt_type': 'parse_figure',
            'base_size': 1280,
            'image_size': 1280,
            'crop_mode': True,
            'custom_prompt': None
        },
        {
            'name': "4️⃣ Parse Figure - GUNDAM MODE 🚀",
            'description': "НОВОЕ: Итеративное сканирование сегментов (1024/640 + crop)",
            'prompt_type': 'parse_figure',
            'base_size': 1024,
            'image_size': 640,  # Меньше для фрагментации!
            'crop_mode': True,
            'custom_prompt': None
        },
        {
            'name': "5️⃣ Parse Figure - LARGE + Структурированный Русский 🇷🇺",
            'description': "НОВОЕ: Large mode + явная инструкция для структурированного извлечения на русском",
            'prompt_type': 'parse_figure',
            'base_size': 1280,
            'image_size': 1280,
            'crop_mode': True,
            'custom_prompt': (
                "Разбери данную BPMN диаграмму структурированно:\n"
                "1. Перечисли все элементы (процессы, события, шлюзы) с их названиями\n"
                "2. Укажи тип каждого элемента (задача, решение, начало, конец)\n"
                "3. Опиши связи между элементами (какие стрелки куда ведут)\n"
                "4. Ответ дай в виде списка на русском языке."
            )
        },
        {
            'name': "6️⃣ Grounded OCR - LARGE + CROP 📍",
            'description': "НОВОЕ: <|grounding|> токен для извлечения с координатами",
            'prompt_type': 'default',
            'base_size': 1280,
            'image_size': 1280,
            'crop_mode': True,
            'custom_prompt': "<image>\n<|grounding|>Extract all text from BPMN diagram elements with bounding boxes. Output in Russian."
        }
    ]
    
    # Выполнение тестов
    results = []
    outputs = {}
    
    for i, test_config in enumerate(tests, 1):
        print(f"\n{Colors.BOLD}{Colors.HEADER}{'─'*100}{Colors.END}")
        print(f"{Colors.BOLD}ТЕСТ {i}/{len(tests)}{Colors.END}")
        
        analysis, raw_output = run_ocr_test(test_config, img_data)
        
        if analysis:
            results.append(analysis)
            outputs[test_config['name']] = raw_output
        
        # Пауза между тестами
        if i < len(tests):
            print(f"\n{Colors.YELLOW}⏳ Пауза 3 сек перед следующим тестом...{Colors.END}")
            time.sleep(3)
    
    # Итоговая сводка
    print_header("📊 ИТОГОВАЯ СВОДКА")
    
    if not results:
        print(f"{Colors.RED}❌ Все тесты провалились{Colors.END}")
        return
    
    # Таблица результатов
    print(f"{Colors.BOLD}Сравнительная таблица:{Colors.END}\n")
    print(f"{'Тест':<50} {'Время':>8} {'BPMN':>6} {'Связи':>7} {'Коорд':>7} {'Оценка':>8}")
    print("─" * 100)
    
    for r in results:
        name_short = r['test_name'][:48]
        time_str = f"{r['time_seconds']:.1f}с"
        bpmn_str = f"✅ {r['bpmn_elements_found']}" if r['bpmn_elements_found'] > 0 else "❌"
        conn_str = f"✅ {r['connections_found']}" if r['connections_found'] > 0 else "❌"
        coord_str = f"✅ {r['coordinate_blocks']}" if r['has_coordinates'] else "❌"
        
        score = r['quality_score']
        if score >= 80:
            score_str = f"{Colors.GREEN}{score}/100{Colors.END}"
        elif score >= 60:
            score_str = f"{Colors.YELLOW}{score}/100{Colors.END}"
        else:
            score_str = f"{Colors.RED}{score}/100{Colors.END}"
        
        print(f"{name_short:<50} {time_str:>8} {bpmn_str:>6} {conn_str:>7} {coord_str:>7} {score_str:>8}")
    
    # Лучший результат
    best = max(results, key=lambda x: x['quality_score'])
    print(f"\n{Colors.BOLD}{Colors.GREEN}🏆 ЛУЧШИЙ РЕЗУЛЬТАТ:{Colors.END}")
    print(f"   {best['test_name']}")
    print(f"   Оценка: {best['quality_score']}/100")
    print(f"   BPMN элементы: {best['bpmn_elements_found']}")
    print(f"   Связи: {best['connections_found']}")
    print(f"   Координаты: {'Да' if best['has_coordinates'] else 'Нет'}")
    print(f"   Время: {best['time_seconds']:.2f} сек")
    
    # Сохранение результатов
    output_dir = Path("output/experiment_b")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # JSON с анализом
    with open(output_dir / "analysis.json", 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # Полные выводы
    for name, output in outputs.items():
        safe_name = name.replace('/', '_').replace(':', '').replace(' ', '_')[:50]
        with open(output_dir / f"{safe_name}.txt", 'w', encoding='utf-8') as f:
            f.write(output)
    
    print(f"\n{Colors.GREEN}✅ Результаты сохранены в: {output_dir}/{Colors.END}")
    
    print_header("✨ ЭКСПЕРИМЕНТ B ЗАВЕРШЕН")

if __name__ == "__main__":
    main()

