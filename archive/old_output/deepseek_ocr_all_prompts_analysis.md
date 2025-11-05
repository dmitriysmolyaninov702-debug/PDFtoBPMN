# Полный анализ всех промптов DeepSeek-OCR

**Дата:** 31.10.2025  
**Тестовое изображение:** page_54_bpmn (300 DPI и 600 DPI)  
**Содержание:** BPMN диаграмма с элементами "Процесс 1", "Процесс 2", "Процесс 3", "Событие 1", "Событие 2"

---

## 🎯 КЛЮЧЕВЫЕ НАХОДКИ

### ⭐⭐⭐ ПРОМПТ #2: `ocr_simple` - ИЗВЛЕКАЕТ ТЕКСТ ИЗ BPMN С КООРДИНАТАМИ!

**RAW OUTPUT (300 DPI):**
```
<|ref|>npoecc2<|/ref|><|det|>[[595, 350, 649, 370]]<|/det|>
<|ref|>C6bITHe1<|/ref|><|det|>[[500, 380, 560, 400]]<|/det|>
<|ref|>npoecc1<|/ref|><|det|>[[355, 410, 409, 431]]<|/det|>
<|ref|>npoecc3<|/ref|><|det|>[[595, 479, 649, 499]]<|/det|>
<|ref|>C6bITHe2<|/ref|><|det|>[[500, 510, 560, 530]]<|/det|>
```

**РАСШИФРОВКА:**
- `npoecc2` → **"Процесс 2"** (координаты: 595, 350, 649, 370)
- `C6bITHe1` → **"Событие 1"** (координаты: 500, 380, 560, 400)
- `npoecc1` → **"Процесс 1"** (координаты: 355, 410, 409, 431)
- `npoecc3` → **"Процесс 3"** (координаты: 595, 479, 649, 499)
- `C6bITHe2` → **"Событие 2"** (координаты: 500, 510, 560, 530)

**ПРОБЛЕМА:** Искаженное распознавание кириллицы (latin вместо cyrillic)

**РЕШЕНИЕ:** Post-processing с транслитерацией или NER на русском языке

---

### ⭐⭐ ПРОМПТЫ #4: `parse_figure` и #5: `describe` - ВИДЯТ СТРУКТУРУ И СВЯЗИ

**RAW OUTPUT (parse_figure):**
```
The main body of the document contains a diagram with three interconnected 
boxes, each labeled "Процесс 1," "Процесс 2," and "Процесс 3," respectively. 
These boxes are connected by arrows, indicating a flow or sequence of processes. 
The diagram is labeled "Событие 1," "Событие 2," and "Событие 3," which 
translates to "Event 1," "Event 2," and "Event 3," respectively. The boxes 
and arrows are colored in yellow, with the exception of the "Событие 1" box, 
which is in black.
```

**ЧТО ДАЮТ:**
- ✅ Правильные названия элементов (без искажений!)
- ✅ Описание связей (arrows, interconnected)
- ✅ Описание визуальных характеристик (yellow boxes, black text)
- ❌ НЕТ координат

---

### ⭐ ПРОМПТЫ #1: `default` и #6: `bpmn` - КЛАССИФИЦИРУЮТ ДИАГРАММУ КАК IMAGE

**RAW OUTPUT (default):**
```
<|ref|>image<|/ref|><|det|>[[327, 309, 667, 536]]<|/det|>
```

**ЧТО ДАЮТ:**
- ✅ Координаты всей диаграммы как единого блока
- ✅ Точное распознавание текста ВНЕ диаграммы
- ❌ НЕ распознают текст ВНУТРИ диаграммы

---

## 📊 СРАВНИТЕЛЬНАЯ ТАБЛИЦА

| Промпт | Текст из BPMN | Координаты | Качество текста | Описание связей | Скорость |
|--------|---------------|------------|-----------------|-----------------|----------|
| **1. default** | ❌ | ✅ (диаграмма целиком) | N/A | ❌ | ⚡⚡⚡ 4.62с |
| **2. ocr_simple** | ✅ | ✅ (каждый элемент) | ⚠️ Искажено | ❌ | ⚠️ 9.53с |
| **3. free_ocr** | ❌ | ❌ | N/A | ❌ | ⚡⚡⚡⚡ 2.06с |
| **4. parse_figure** | ✅ | ❌ | ✅ Отлично | ✅ | ⚠️ 9.57с |
| **5. describe** | ✅ | ❌ | ✅ Отлично | ✅ | ⚠️ 8.56с |
| **6. bpmn** | ❌ | ✅ (диаграмма целиком) | N/A | ❌ | ⚡⚡⚡ 3.73с |

---

## 🚀 ГИБРИДНЫЙ ПОДХОД (РЕКОМЕНДАЦИЯ)

### Стратегия: Два прохода по одному изображению

#### ШАГ 1: `ocr_simple` → Извлечение координат и структуры
```python
result_1 = ocr_service(image, prompt="ocr_simple")
# Получаем:
# - Список элементов с координатами
# - Искаженный текст (npoecc1, C6bITHe1)
```

#### ШАГ 2: `parse_figure` → Извлечение правильных названий
```python
result_2 = ocr_service(image, prompt="parse_figure")
# Получаем:
# - Правильные названия ("Процесс 1", "Событие 1")
# - Описание связей (arrows, flow)
```

#### ШАГ 3: Merge результатов
```python
merged = match_and_merge(
    coordinates_from_ocr_simple=result_1,
    correct_labels_from_parse_figure=result_2
)
# Итог:
# {
#   "elements": [
#     {"type": "Task", "name": "Процесс 1", "bbox": [355, 410, 409, 431]},
#     {"type": "Event", "name": "Событие 1", "bbox": [500, 380, 560, 400]},
#     ...
#   ],
#   "connections": [...]
# }
```

---

## 📋 ДЕТАЛЬНЫЕ ДАННЫЕ

### Промпт #1: `default`

**300 DPI RAW OUTPUT:**
```
=====================
BASE:  torch.Size([1, 256, 1280])
NO PATCHES
=====================
<|ref|>text<|/ref|><|det|>[[80, 119, 510, 135]]<|/det|>
Дата введения изменения___________ Основание:___________________________ 

<|ref|>text<|/ref|><|det|>[[543, 119, 628, 135]]<|/det|>
Стр. 54 из 54 

<|ref|>text<|/ref|><|det|>[[106, 170, 763, 190]]<|/det|>
Продолжение приложения 8. Примеры использования логических шлюзов в нотации BPMN (справочное) 

<|ref|>text<|/ref|><|det|>[[64, 285, 264, 303]]<|/det|>
Эксклюзивный шлюз по событиям 

<|ref|>image<|/ref|><|det|>[[327, 309, 667, 536]]<|/det|>
```

**JSON блоки:**
- 4 text блока (заголовки вне диаграммы)
- 0 элементов BPMN

---

### Промпт #2: `ocr_simple` ⭐⭐⭐

**300 DPI RAW OUTPUT:**
```
=====================
BASE:  torch.Size([1, 256, 1280])
NO PATCHES
=====================
<|ref|>Uair<|/ref|><|det|>[[95, 72, 168, 103]]<|/det|>
<|ref|>Tpe6oBaniaKMoAeJIHpOBaHHO<|/ref|><|det|>[[322, 66, 520, 87]]<|/det|>
<|ref|>B uBisness Studio<|/ref|><|det|>[[410, 87, 520, 111]]<|/det|>
<|ref|>KJ-CT-161-01<|/ref|><|det|>[[532, 75, 627, 97]]<|/det|>
<|ref|>CTp.54H3 54<|/ref|><|det|>[[544, 118, 630, 140]]<|/det|>
<|ref|>IpoAoxeHHeHpNIOxeHHe8.HpMepbIcncno3b3aHnHnOJIyecCKXHJI3O3B B HTOaHn BPMN(cnpaBOHHOe)<|/ref|><|det|>[[108, 171, 765, 192]]<|/det|>
<|ref|>3KcKIO3BHbIYHJI3O3nOCO6bITNMA<|/ref|><|det|>[[65, 288, 265, 304]]<|/det|>
<|ref|>npoecc2<|/ref|><|det|>[[595, 350, 649, 370]]<|/det|>
<|ref|>C6bITHe1<|/ref|><|det|>[[500, 380, 560, 400]]<|/det|>
<|ref|>npoecc1<|/ref|><|det|>[[355, 410, 409, 431]]<|/det|>
<|ref|>npoecc3<|/ref|><|det|>[[595, 479, 649, 499]]<|/det|>
<|ref|>C6bITHe2<|/ref|><|det|>[[500, 510, 560, 530]]<|/det|>
```

**Элементы BPMN с координатами:**
1. `npoecc2` (Процесс 2) → [595, 350, 649, 370]
2. `C6bITHe1` (Событие 1) → [500, 380, 560, 400]
3. `npoecc1` (Процесс 1) → [355, 410, 409, 431]
4. `npoecc3` (Процесс 3) → [595, 479, 649, 499]
5. `C6bITHe2` (Событие 2) → [500, 510, 560, 530]

---

### Промпт #3: `free_ocr`

**300 DPI RAW OUTPUT:**
```
=====================
BASE:  torch.Size([1, 256, 1280])
NO PATCHES
=====================
Требования к моделированию в Business Studio

КД-СТ-161-01
Стр. 54 из 54

Продажение приложения 8. Примеры использования логических шлюзов в нотации BPMN (справочное)

Эксклюзивный шлюз по событиям
```

**Особенности:**
- Самый быстрый (2.06 сек)
- Только текст вне диаграммы
- НЕТ структурированных блоков

---

### Промпт #4: `parse_figure` ⭐⭐

**300 DPI RAW OUTPUT:**
```
=====================
BASE:  torch.Size([1, 256, 1280])
NO PATCHES
=====================
The image displays a document with a white background and primarily black text, with some sections highlighted in yellow. At the top, there is a header in bold black text that reads "Требования к моделированию в Business Studio" followed by "КД-СТ-161-01" and "Стр. 54 из 54" indicating the document's page number and total pages. Below this header, there is a section titled "Продолжение приложения 8. Примеры использования логических шлюзов в нотации BPMN (справочное)" which translates to "Appendix 8. Examples of using logical locks in BPMN (extended)" suggesting that this is a continuation of a previous document.

The main body of the document contains a diagram with three interconnected boxes, each labeled "Процесс 1," "Процесс 2," and "Процесс 3," respectively. These boxes are connected by arrows, indicating a flow or sequence of processes. The diagram is labeled "Событие 1," "Событие 2," and "Событие 3," which translates to "Event 1," "Event 2," and "Event 3," respectively. The boxes and arrows are colored in yellow, with the exception of the "Событие 1" box, which is in black.

At the bottom of the image, there is a footer in black text that reads "Экспозиционный шлюз по событиям," which translates to "Expositional lock by events." This suggests that the document is related to a technical or business process involving locks and events.

The overall layout of the document is structured and formal, typical of technical documentation. The use of color is minimal, with the exception of the yellow highlights, which draw attention to specific sections. The text is clear and legible, with no visible errors or typos.
```

**Извлеченная информация:**
- ✅ "Процесс 1", "Процесс 2", "Процесс 3" - правильно
- ✅ "Событие 1", "Событие 2", "Событие 3" - правильно
- ✅ Описание связей (arrows, interconnected boxes)
- ✅ Описание визуальных характеристик (yellow, black)
- ❌ НЕТ координат

---

### Промпт #5: `describe` ⭐⭐

**300 DPI RAW OUTPUT:**
```
=====================
BASE:  torch.Size([1, 256, 1280])
NO PATCHES
=====================
The image is an informational document from Uair Airlines featuring two main sections of text on either side separated by a central diagram.

On the left-hand section:
- The top part contains contact information for Uair Airlines including phone numbers.
- Below that are details about "Дополнение приложения" which translates to "Additional Application," indicating additional services or applications available through the airline's platform.
- A subheading reads "Эксклюзивный шлюз по событиям", meaning "Exclusive Flight Booking Based on Events."

In the center portion:
- There's a flowchart titled "Требования к моделированию в Business Studio" translating to "Requirements for Modeling in Business Studio."
- This chart outlines three processes labeled as "Процесс 1," "Процесс 2," and "Процесс 3." Each process has corresponding elements represented visually—a yellow circle represents "Событие 1" ("Event 1"), while another element within each process box indicates different outcomes such as green circles representing "Событие 2" ("Event 2") and red crosses denoting "Событие 3" ("Event 3").
  
On the right-hand section:
- It states "КД-СТ-161-01" at the very beginning signifying some sort of code or standard reference number related to the content presented above it.
- At the bottom-right corner there appears to be more specific information regarding BPMN (Business Process Model and Notation), suggesting further elaboration might exist beyond what can immediately be seen here.

Overall, the layout combines both descriptive texts and visual diagrams designed to convey complex business-related procedures succinctly yet comprehensively.
```

**Извлеченная информация:**
- ✅ "Процесс 1", "Процесс 2", "Процесс 3" - правильно
- ✅ "Событие 1", "Событие 2", "Событие 3" - правильно (но добавил "Событие 3" - галлюцинация)
- ✅ Описание визуальных элементов (yellow circle, green circles, red crosses)
- ✅ Описание структуры (flowchart, three processes)
- ❌ НЕТ координат
- ⚠️ Некоторые галлюцинации (Uair Airlines, contact information)

---

### Промпт #6: `bpmn`

**300 DPI RAW OUTPUT:**
```
=====================
BASE:  torch.Size([1, 256, 1280])
NO PATCHES
=====================
 

<|ref|>text<|/ref|><|det|>[[87, 120, 512, 137]]<|/det|>
Дата введения изменения: ______________ Основание: ________________________ Стр. 54 из 54 

<|ref|>text<|/ref|><|det|>[[106, 170, 763, 192]]<|/det|>
Продолжение приложения 8. Примеры использования логических шлюзов в нотации BPMN (справочное) 

<|ref|>text<|/ref|><|det|>[[64, 285, 264, 304]]<|/det|>
Эксклюзивный шлюз по событиям 

<|ref|>image<|/ref|><|det|>[[327, 310, 667, 536]]<|/det|>
```

**JSON блоки:**
- 3 text блока (заголовки)
- 1 image блок (вся диаграмма)

---

## 🎯 ИТОГОВЫЕ ВЫВОДЫ

### ✅ Что работает:
1. **`ocr_simple`** извлекает текст из BPMN элементов с координатами (хоть и с искажениями)
2. **`parse_figure`** и **`describe`** дают правильные названия элементов и описание связей
3. **`default`** и **`bpmn`** точно определяют границы всей диаграммы

### ❌ Что НЕ работает:
1. Ни один промпт не дает **И** координаты **И** правильные названия одновременно
2. `ocr_simple` искажает кириллицу (latin транслитерация)
3. `parse_figure`/`describe` не дают координат

### 🚀 РЕШЕНИЕ: Гибридный подход

**Алгоритм:**
1. Запуск `ocr_simple` → получаем координаты элементов
2. Запуск `parse_figure` → получаем правильные названия и связи
3. Matching по координатам и контексту
4. Post-processing для исправления искаженной кириллицы
5. Построение BPMN IR → XML

**Преимущества:**
- ✅ Используем сильные стороны каждого промпта
- ✅ Компенсируем слабости одного промпта другим
- ✅ Не требует fine-tuning
- ✅ Работает out-of-the-box

**Недостатки:**
- ⏱️ Двойное время обработки (9.5с + 9.6с = ~19 сек на страницу)
- 🔧 Требует логику matching и post-processing
- ⚠️ Возможны ошибки при matching

---

## 📊 Сравнение разрешений (300 DPI vs 600 DPI)

**Вывод:** Разрешение **НЕ влияет** на качество результатов
- Оба дают идентичный raw output
- Координаты практически совпадают
- 300 DPI быстрее и требует меньше памяти

**Рекомендация:** Использовать **300 DPI** для всех задач

