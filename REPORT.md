# HardwareResearch AI — Schema v2: порівняльний звіт

Дата: **26.10.2026**. **120/120 primary attempts, 8/8 конфігурацій, 10/10 approved golden.** Реальні результати й оцінки завершені. Автор погодив умовну production-рекомендацію та компроміси 26.10.2026.

## Задача й відтворюваність

Schema v1 витягувала довільні описи компонентів/параметрів, для яких точне зіставлення надто залежало від формулювань. Schema v2 спрощує задачу до восьми enum/bool/list[enum] полів. Це інша задача: v1 Full Fact F1 компонентів не порівнюється з v2 F1 тегів платформ.

Виходи v1 і 30 original TXT збережені. `--schema-version v2` явно обирає новий контракт, без зміни v1 default. Той самий prepared input/hash використаний у всіх моделях, промптах і sampling для кожного ID. Підготовка schema-v2-text-v1 видаляє тільки початковий відомий site header, не домішує manifest topic/language/tags і не переписує джерела.

Golden version: `golden-v2-1`; SHA-256: `9a3b831cee329deaf1a8175c0a1e581a0fc9e253d2807a27d08b4fab74c71a5a`. Людські рішення з доказами — [review ledger](data/golden_v2_review.md). Правила: `schema-v2-mentions-v1`, SHA-256 `921ee328bcb92a6d37c3ef6aea7330fa01fae65504fdecad9af61ccaec62ac92`. Evaluator policy: `schema-v2-evaluator-v1.0`; hashes коду, джерел та runs — [summary.json](results/schema_v2/evaluation-final/summary.json).

## Корпус і незалежність

30 TXT: **18 uk / 9 en / 3 ru**. Golden G=10 має ті самі ID, що історичний golden v1, але нові мітки вручну перевірено за TXT. Header видалено у 9 en TXT. Приклади без окремих ознак: HR-0207 не називає enum-платформи/інтерфейси, але має акумулятор; HR-0187 містить sensor, без battery/display і явного фізичного motor.

| Текст | Min Unicode-довжина | Max Unicode-довжина |
| --- | --- | --- |
| Original | 863 (HR-0187) | 19719 (HR-0001) |
| Prepared | 863 (HR-0187) | 19719 (HR-0001) |

Метод: len(UTF-8 decoded string), Unicode code points, не bytes/слова/графеми. Original — read_bytes().decode; prepared — після нормалізації CRLF/CR→LF і видалення header. Довжини й hashes кожного ID — [plan.json](results/schema_v2/plan.json).

Реальний noise/typo: HR-0068:42 «Приемр проекта»; HR-0244:30 «на пркилад», :90 «ції меережі»; HR-0743:83–90 таблиця з generic «Стовпець» у англійському тексті; HR-0227:95 експортовані зворотні слеші в SPEED OF REACTION. Рядки — у незмінених original TXT. Не приписували корпусу відсутні види шуму.

Спірні теми людина погодила: HR-0244→sensors_measurements (мета — виміряти вагу), HR-0385→devices_automation (автополив), HR-0212→power_batteries (резервне живлення), HR-0227→sensors_measurements (фільтрація вимірів).

D={HR-0056, HR-0055, HR-0001, HR-0221} обрано серед20 non-golden до запусків; D∩G=∅. Для tuning вручну прочитано3 повні TXT: HR-0056, HR-0055, HR-0221; HR-0001 не використано як tuning example. [Development notes](results/schema_v2/development_notes.md) посилаються лише на реальні D baseline runs. Prompt-v2 frozen після60 baseline і до першої нової оцінки G; після freeze його не редагували. Попередня розробка v1/evaluator вже бачила G, тому цей експеримент не є повністю сліпим holdout.

## Матриця та головні метрики

T0=(temperature=0,top_p=1); T07=(0.7,1). Actual sent Settings/payload metadata узгоджені. Сервер не повертає effective sampling: прийняття запиту й збережене sent значення не видаються за окремо виміряний effective parameter. Чотири реальні probes2×2 успішні й виключені з primary/quality/latency.

Quality завжди на **G=10**: per-field correct/G; aggregate correct/(8G)=/80; content без language correct/(7G)=/70. Списки: exact set accuracy та окремі micro TP/FP/FN/P/R/F1. Порядок не впливає; missing/invalid не дорівнює false/[] й не зникає зі знаменника; нульовий знаменник PRF→null. Failed primary не повторювали для заміни кращою відповіддю.

| Конфігурація | N planned/received/missing | Content /70 | Aggregate /80 | Language /10 |
| --- | --- | --- | --- | --- |
| GPT-v1-T0 | 30/30/0 | 62/70 (88.57%) | 72/80 (90.00%) | 10/10 |
| OSS-v1-T0 | 30/30/0 | 29/70 (41.43%) | 36/80 (45.00%) | 7/10 |
| GPT-v1-T07 | 10/10/0 | 62/70 (88.57%) | 72/80 (90.00%) | 10/10 |
| OSS-v1-T07 | 10/10/0 | 35/70 (50.00%) | 42/80 (52.50%) | 7/10 |
| GPT-v2-T0 | 10/10/0 | 62/70 (88.57%) | 72/80 (90.00%) | 10/10 |
| OSS-v2-T0 | 10/10/0 | 30/70 (42.86%) | 37/80 (46.25%) | 7/10 |
| GPT-v2-T07 | 10/10/0 | 62/70 (88.57%) | 72/80 (90.00%) | 10/10 |
| OSS-v2-T07 | 10/10/0 | 24/70 (34.29%) | 28/80 (35.00%) | 4/10 |

G coverage **10/10 у кожній конфігурації**. N=30 у двох baseline не підміняє G; решта N=10. First/final валідність нижче — тільки G.

## Точність кожного поля

| Конфігурація | language | primary_topic | platforms | interfaces | sensor | display | battery | motor |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GPT-v1-T0 | 10/10 | 10/10 | 9/10 | 7/10 | 8/10 | 9/10 | 10/10 | 9/10 |
| OSS-v1-T0 | 7/10 | 3/10 | 3/10 | 4/10 | 4/10 | 6/10 | 4/10 | 5/10 |
| GPT-v1-T07 | 10/10 | 10/10 | 9/10 | 7/10 | 8/10 | 9/10 | 10/10 | 9/10 |
| OSS-v1-T07 | 7/10 | 3/10 | 6/10 | 4/10 | 4/10 | 7/10 | 6/10 | 5/10 |
| GPT-v2-T0 | 10/10 | 10/10 | 9/10 | 7/10 | 8/10 | 9/10 | 10/10 | 9/10 |
| OSS-v2-T0 | 7/10 | 4/10 | 4/10 | 0/10 | 6/10 | 5/10 | 6/10 | 5/10 |
| GPT-v2-T07 | 10/10 | 9/10 | 9/10 | 8/10 | 8/10 | 9/10 | 10/10 | 9/10 |
| OSS-v2-T07 | 4/10 | 2/10 | 3/10 | 1/10 | 5/10 | 4/10 | 5/10 | 4/10 |

## Списки: micro precision/recall/F1

| Конфігурація | Platforms TP/FP/FN | Platforms P/R/F1 | Interfaces TP/FP/FN | Interfaces P/R/F1 |
| --- | --- | --- | --- | --- |
| GPT-v1-T0 | 9/0/1 | 1.000/0.900/0.947 | 3/0/4 | 1.000/0.429/0.600 |
| OSS-v1-T0 | 5/2/5 | 0.714/0.500/0.588 | 5/5/2 | 0.500/0.714/0.588 |
| GPT-v1-T07 | 9/0/1 | 1.000/0.900/0.947 | 3/0/4 | 1.000/0.429/0.600 |
| OSS-v1-T07 | 7/1/3 | 0.875/0.700/0.778 | 3/5/4 | 0.375/0.429/0.400 |
| GPT-v2-T0 | 9/0/1 | 1.000/0.900/0.947 | 4/1/3 | 0.800/0.571/0.667 |
| OSS-v2-T0 | 6/1/4 | 0.857/0.600/0.706 | 3/21/4 | 0.125/0.429/0.194 |
| GPT-v2-T07 | 9/0/1 | 1.000/0.900/0.947 | 5/2/2 | 0.714/0.714/0.714 |
| OSS-v2-T07 | 3/0/7 | 1.000/0.300/0.462 | 1/11/6 | 0.083/0.143/0.105 |

## Валідність, latency, usage і вартість на golden_10

A_G=10 отриманих primary у кожному рядку. V_G/A_G і V_G/G показані окремо; first — confirmed valid first attempt/A_G. Repaired — успішна відповідь після однієї repair-генерації; failed лишаються в усіх знаменниках.

| Конфігурація | First/A_G | V_G/A_G | V_G/G | Repaired/failed | p50/p95, с (n) | Input/output tokens | API $/1000 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GPT-v1-T0 | 10/10 | 10/10 | 10/10 | 0/0 | 1.324/1.506 (10) | 23810/467 | 0.308 |
| OSS-v1-T0 | 7/10 | 7/10 | 7/10 | 0/3 | 3.239/28.404 (10) | 15634/8762 | 0 external; hardware unknown |
| GPT-v1-T07 | 10/10 | 10/10 | 10/10 | 0/0 | 1.325/1.670 (10) | 23810/467 | 0.266 |
| OSS-v1-T07 | 6/10 | 8/10 | 8/10 | 2/2 | 3.098/3.785 (10) | 20150/939 | 0 external; hardware unknown |
| GPT-v2-T0 | 10/10 | 10/10 | 10/10 | 0/0 | 1.405/1.510 (10) | 27250/471 | 0.376 |
| OSS-v2-T0 | 4/10 | 7/10 | 7/10 | 3/3 | 3.783/29.777 (10) | 26424/12995 | 0 external; hardware unknown |
| GPT-v2-T07 | 10/10 | 10/10 | 10/10 | 0/0 | 1.452/1.505 (10) | 27250/474 | 0.250 |
| OSS-v2-T07 | 5/10 | 5/10 | 5/10 | 0/5 | 3.355/17.419 (10) | 27793/4977 | 0 external; hardware unknown |

Latency — pipeline wall time, включає записані retry/repair, не включає запис файла; квантілі лінійні (n−1)q. Known n=10 і missing=0 для кожного G рядка. Cold start=unknown: контрольований cold benchmark/warmup не виконувалися, перші probe latency не домішані в primary. First-generation latency окремо не агрегувалась; жодного твердження про cold speedup немає.

Usage сумує фактичні HTTP requests без дублювання attempt.usage; для наведених primary token usage відомий. $/1000 — mean повного pipeline cost на цих10 документах×1000; припущено ту саму довжину input/output і cache mix. Тариф 26.10.2026: input $0.15/M, cached $0.075/M, output $0.60/M, [офіційна документація GPT-4o mini](https://developers.openai.com/api/docs/models/gpt-4o-mini). Exact requested/returned route і tariff source збережені в [pricing-final.json](results/schema_v2/pricing-final.json). Відмінність $/1000 між T0/T07 не доводить дешевизну temperature: cached tokens і порядок запуску різні. Для Ollama external API=0, обладнання/електрика та повна вартість невідомі.

## Baseline all_30 — окремо від порівняння G

| Baseline | Success/repaired/failed | First/final valid | p50/p95, с (n) | Input/output tokens |
| --- | --- | --- | --- | --- |
| GPT-v1-T0 | 30/0/0 | 30/30 → 30/30 | 1.366/1.648 (30) | 77857/1425 |
| OSS-v1-T0 | 17/3/10 | 17/30 → 20/30 | 3.362/28.554 (30) | 58262/34563 |

All_30 — descriptive runtime/validity, не додатковий quality benchmark. Зокрема валідність llama3.2:3b на повних30 відрізняється від subset G.

## Ефект prompt-v2 і sampling

У GPT content не змінився: **62/70 у всіх4 конфігураціях**. T0 interfaces recall зріс із3/7=0.429 до4/7=0.571, але з’явився1 FP; interfaces F1 зріс0.600→0.667 без росту exact field accuracy. T07 v2 дав recall5/7=0.714 і2 FP; primary_topic впав10/10→9/10, aggregate знову той самий. У Llama T0 content29→30/70, T07 content35→24/70; prompt-v2 не дав стабільного покращення, і T07 не є універсальним виправленням. Prompt не редагувався після цих спостережень.

## П’ять реальних помилок

### 1. GPT-v1-T0 / HR-0068 / mentioned_interfaces

Джерело: 12,54,58: USB прямо названий. Expected: `["usb"]`; final predicted: `[]`. Пропущено другорядний інтерфейс. JSON валідний, але recall неповний.

Raw: [run_56a3b652e9f94909a135db2f86acb48f.json](results/schema_v2/GPT-v1-T0/run_56a3b652e9f94909a135db2f86acb48f.json); [деталі](results/schema_v2/evaluation-final/details.json).

### 2. GPT-v1-T0 / HR-0187 / mentions_motor

Джерело: 3,11: помпа; 21–35 motor — тільки ім’я змінної. Expected: `false`; final predicted: `true`. Модель приписала фізичний двигун за помпою/ідентифікатором. За погодженим mention rule цього недостатньо.

Raw: [run_67127d93ba254784be65d14d6e28712e.json](results/schema_v2/GPT-v1-T0/run_67127d93ba254784be65d14d6e28712e.json); [деталі](results/schema_v2/evaluation-final/details.json).

### 3. GPT-v1-T0 / HR-0212 / mentions_display

Джерело: 24,71: індикація звичайними LED, апаратного дисплея немає. Expected: `false`; final predicted: `true`. Підміна LED-індикації дисплеєм — false positive.

Raw: [run_dbb26dae49504d46b0270f31cb68aa0a.json](results/schema_v2/GPT-v1-T0/run_dbb26dae49504d46b0270f31cb68aa0a.json); [деталі](results/schema_v2/evaluation-final/details.json).

### 4. OSS-v1-T0 / HR-0254 / mentioned_interfaces

Джерело: 11,17,35,45: I2C. Expected: `["i2c"]`; final predicted: `null`. Після stop перша генерація має дубль i2c, repair теж лишає дублікати. Локальна унікальність не послаблюється: final failed.

Raw: [run_88620ac6f51b422d8ff6e260545a3394.json](results/schema_v2/OSS-v1-T0/run_88620ac6f51b422d8ff6e260545a3394.json); [деталі](results/schema_v2/evaluation-final/details.json).
Спостережені finish reasons: `['stop', 'stop']`; raw першої генерації 237 Unicode-символів. Expected не змінено під цей результат.

### 5. OSS-v1-T0 / HR-0385 / language

Джерело: 11–17: англійський текст. Expected: `"en"`; final predicted: `null`. API finish_reason=length, повторювання arduino у масиві до ліміту. Truncation не ремонтується й не видається за валідний прогноз; final failed, усі8 полів incorrect.

Raw: [run_f6937e0ab6df428188decb6a5dee68a3.json](results/schema_v2/OSS-v1-T0/run_f6937e0ab6df428188decb6a5dee68a3.json); [деталі](results/schema_v2/evaluation-final/details.json).
Спостережені finish reasons: `['length']`; raw першої генерації 15021 Unicode-символів. Expected не змінено під цей результат.

## Висновок після додаткового прогону з prompt-v3

26.10.2026 виконано ще **60 primary attempts**, по 30 на OpenAI `gpt-4o-mini` та Ollama `llama3.2:3b`, із Schema v2, temperature=0 і top_p=1. Це окремий експеримент понад початкову матрицю120. Використано ту саму підготовку текстів і approved golden G=10. Hash поточного v3 збігався з попереднім Ollama-тестом; ці запуски є новим повторним вимірюванням, а не свідченням зміни тексту промпту.

| Модель | Content accuracy на G10 | Aggregate accuracy на G10 | Success / repaired / failed на N30 | JSON first → final на N30 | p50 / p95, с на N30 |
| --- | --- | --- | --- | --- | --- |
| GPT-4o mini | 62/70 (88.57%) | 72/80 (90.00%) | 29 / 0 / 1 | 29/30 → 29/30 | 1.609 / 2.632 |
| Llama3.2:3b | 28/70 (40.00%) | 31/80 (38.75%) | 16 / 4 / 10 | 16/30 → 20/30 | 3.356 / 29.173 |

**Prompt-v3 не дав виміряного покращення content accuracy.** У GPT залишилося62/70, як у попередніх v1/v2. Порівняно з v1/T0 sensor accuracy зросла8/10→9/10, але exact accuracy інтерфейсів знизилася7/10→6/10; interfaces precision знизилася1.000→0.750 за того самого recall3/7. Отже, покращення одного поля компенсоване погіршенням іншого. Для Llama результат28/70 нижчий за попередні T0:29/70 у v1 та30/70 у v2. На одному прогоні й10 відомих еталонах це не доводить статистичної переваги або регресії версії.

Проблема структурної надійності залишилася навіть за явної інструкції не дублювати теги. GPT не виправив повтори `arduino` у HR-0640 після repair, тому цей primary залишився failed. У Llama6 невдач спричинені дублями після repair, ще4 — обривом на4096 вихідних токенах. Усі невдалі результати збережені й враховані у знаменниках. Збільшення ліміту токенів саме по собі не усуває дублікати або вигадані факти.

**Погоджена рекомендація GPT-v1-T0 залишається чинною:** для сценарію індексації з пріоритетом точності тегів v3 не показав переваги за загальною якістю, а precision інтерфейсів і валідність на всіх30 погіршилися в цьому вимірюванні. Подальші зміни промпту варто перевіряти на незалежних non-golden текстах із контролем FP/FN та repair, а не підганяти під цей G.

Витрати OpenAI саме цього додаткового прогону за token/cache usage й тарифом — **$0.01143105**; для Ollama зовнішня API-плата нульова, вартість обладнання/електрики невідома. Latency включає repair; моделі запускалися паралельно, cold start не вимірювався. Результати початкової матриці й її кошторис нижче не змінені.

Докази: [повне порівняння v3](results/schema_v2/comparison_v3_20261026_edbedd85/comparison.md), [strict summary](results/schema_v2/comparison_v3_20261026_edbedd85/evaluation/summary.json), [помилки по полях](results/schema_v2/comparison_v3_20261026_edbedd85/evaluation/details.json). Prompt SHA-256: `f45f5854945d838277869421bed26a8cc1480082c5a7628c71896e9f3a439f7e`.

## Рекомендована конфігурація для production

**Погоджено автором 26.10.2026: GPT-v1-T0.** Сценарій HardwareResearch AI — первинна індексація технічних статей для пошуку/RAG із пріоритетом не приписувати непідтверджені платформи й інтерфейси. Це умовна практична рекомендація на наявних даних, не доведена статистична перевага.

Конкретний маршрут: provider=`openai`, requested model=`gpt-4o-mini` (фактично повернуто `gpt-4o-mini-2024-07-18`), schema=`v2`, schema SHA-256=`8072bc4bea0cd5fd7d25cd2bda031de58b6acd1fad967d21c7e0e1e24c739c31`; prompt=`schema_v2/v1`, SHA-256=`7dc02d743950aa524fe4dc36f0804d433c88617672d2abe14b221fe358dfc5f5`; temperature=`0`, top_p=`1`.

Чому: порівняно всі8 фактично запущених конфігурацій. GPT забезпечив100% first/final JSON validity, content62/70 проти максимум35/70 у OSS і p50 близько1.32с. V1/T0 має100% precision платформ/інтерфейсів на G, topic10/10 і дешевший короткий prompt. У v2 той самий content, але з’явилися FP інтерфейсів; у T07/v2 додатково9/10 topic. Нижча cache-залежна вартість окремого T07 рядка не є доказом переваги sampling.

Компроміс: у вибраному варіанті interfaces recall лише3/7=42.86%, platform recall9/10, sensor accuracy8/10, є false positive motor/display. Тому рекомендація стосується індексації з контрольованими пропусками й подальшим review, не автономних рішень про комплектацію/безпеку. Для recall-critical пошуку цей baseline недостатній: розглянути v2/T07 як окрему гіпотезу або додаткову перевірку пропусків, з більшим незалежним набором і контролем FP. Локальний OSS варіант доречний лише за вимоги локальності/відсутності зовнішнього API й ручної перевірки, а не як рівноцінна якість.

Умови перегляду: нові незалежні документи/шуми/мовний розподіл; неприйнятні пропуски інтерфейсів; зміна моделі/alias snapshot, API-доступності, тарифів або бюджету; зміна схеми/підготовки input чи requirements локальності. Перевіряти на іншому non-golden наборі; не підганяти цей G. Один запуск на10 еталонах не доводить статистичної значущості чи стабільності повторень.

**Авторський review: виконано.** Користувач відповів «погоджую» на конкретну конфігурацію, сценарій індексації з пріоритетом точності тегів та явно зазначений низький recall інтерфейсів.

## Повнота обліку, витрати і перевірки

Primary: 120 run files, 136 генерацій, із них 16 repair; 136 HTTP, 0 транспортних retry. Probes окремо: 4 files, 4 генерацій, 4 HTTP. Probes не входять у120/G/runtime таблиць.

Фактичний token/cache usage × датований тариф: **$0.019617** для всіх нових OpenAI primary/probes/repair/retry; unknown usage reserve=$0.000000. Із погодженого залишку$4.95 розрахунково лишається **$4.930383**. Це облік заusage, не запит балансу billing account. Подробиці по кожному run — [budget_ledger.json](results/schema_v2/budget_ledger.json).

158 offline unittest пройшли після human approval/freeze; mock demo/30/10 і незалежний offline evaluator перевірені. Матриця120/planned ID, strict golden10, всі source/input/schema/prompt hashes перевірені; вісім індивідуальних evaluations і загальне порівняння мають той самий golden/rules/policy. Усі108 protected hashes незмінні за фінальним acceptance. Optional240/cold benchmark/product scheduler не виконувалися; службова команда зберігала partial runs і не повторювала primary.

Відтворення без API:

```powershell
.\.venv\Scripts\python.exe evaluate_v2.py --golden data/sourses/hm1/golden_v2.json --runs results/schema_v2/GPT-v1-T0 results/schema_v2/OSS-v1-T0 results/schema_v2/GPT-v1-T07 results/schema_v2/OSS-v1-T07 results/schema_v2/GPT-v2-T0 results/schema_v2/OSS-v2-T0 results/schema_v2/GPT-v2-T07 results/schema_v2/OSS-v2-T07 --output-dir results/schema_v2/NEW-EVALUATION --strict-golden --pricing results/schema_v2/pricing-final.json
```

Output має бути новим/порожнім. Збережені primary і старі результати не перезаписуються. Git-коміт не створювався.
