# Schema v2 — контракт і запуск

Дата: 26.10.2026. Статус: реалізація й обов’язкова матриця120 завершені;4 реальні probes,10 approved golden,8 strict evaluations; production-рекомендацію погодив автор.

## Контракт

Вісім required полів: `language` (uk/en/ru), `primary_topic` (8 категорій v1), `mentioned_platforms`, `mentioned_interfaces`, `mentions_sensor`, `mentions_display`, `mentions_battery`, `mentions_motor`.

Платформи у canonical order: arduino, esp32, esp8266, stm32, raspberry_pi, orange_pi. Інтерфейси: wifi, bluetooth, lora, i2c, spi, uart, usb. Невідомі значення відхиляються, не мапляться на найближчий enum. Bool суворий: 0/1/рядки не приймаються. Null, missing, extra поля й дублікати списків заборонені. Валідна перестановка канонізується без repair; raw незмінний. Порожній список і false — допустимі підтверджені відсутності, missing run — помилка всіх восьми полів.

`src/schemas` містить реєстр SchemaSpec; v1 реекспортує початкову модель без зміни `src/schema.py`. JSON Schema в API та її SHA-256 беруться з одного descriptor. Унікальність тегів — локальний Pydantic validator: `uniqueItems` не надсилається до API; required/enum/extra/type обмежені також API schema. Одне repair не заміняє HTTP retry; refusal/truncation/HTTP error не стають success через правильний JSON.

## Змістова область й правила

[rules_version schema-v2-mentions-v1](../data/golden_annotation_rules_v2.md) описує згадки, а не встановлену комплектацію: «без Bluetooth» містить згадку; Arduino IDE/Cloud/виробник сам по собі не Arduino-платформа; Wemos не означає ESP8266 без прямої згадки. Wire/Serial/TX/RX не виводять I2C/UART. LoRaWAN без LoRa не дає lora. Sensor bare model без пояснення, звичайний LED, помпа без опису двигуна й випадкові імена змінних не доводять bool. Метафора «двигун прогресу» не електродвигун. Код/заголовок/основний текст враховуються; site header/навігація — ні. Cloud dashboard/графік на комп’ютері сам не означає апаратного дисплея.

`schema-v2-text-v1` нормалізує переноси CRLF/CR → LF і видаляє тільки відомий початковий header: після першого непорожнього title три наступні непорожні рядки `Автори:`, `Категорії:`, `Плати:` із значеннями. Видаляються тільки ці три рядки. Часткові блоки, слова в абзацах, цитатах і code збережені. Оригінальні bytes не переписуються. Процедура однакова в single/30/10 режимах; manifest language/topic/tags і expected не додаються в user text. План містить source_sha256, input_text_sha256 і preparation version для всіх 30 файлів; видалений header не може бути доказом у golden. Зміна input означає інший експеримент, label-only зміна — offline перерахунок збережених runs.

## Керування запуском

Основні команди наведено в [README](../README.md). `--schema-version v2` автоматично обирає baseline `schema_v2/v1`; v1 default збережений. `--document-ids` приймає UTF-8 список рівно 10 унікальних manifest ID й несумісний з `--document`/`--all-documents`. Температура `[0,2]`, top_p `(0,1]`, без NaN/Infinity; CLI overrides тільки задані поля, нуль не губиться, ідентичні Settings йдуть до payload та metadata всіх трьох клієнтів. .env не переписується.

Run містить schema version/hash, prompt namespace/version/hash, source/input/preparation, sampling, provider/requested model, raw attempts, validity/status/usage/latency. Для v2 output новий/порожній; старі step1/step2/evaluation і inputs захищені. `experiment_manifest.json` містить planned IDs і processed count. Failed primary є обробленою невдачею; missing/not_processed — partial. Probe/warmup зберігаються окремо з kind й не приймаються primary evaluator. Автоматичного scheduler/resume немає; після зупинки старі файли не перезаписувати й не вибирати кращу повторну відповідь.

## Offline evaluator

`evaluate_v2.py` не читає .env, не створює мережевих запитів і не імпортує semantic scorer. Потрібні v2 golden і окремі run-каталоги з experiment_manifest. Schema/hash/config/ID дублікати й змішані каталоги діагностуються. `evaluate.py` залишається v1 і явно відхиляє v2. Звичайна оцінка незатверджених міток provisional; strict потребує approved. Поточний golden — незалежно підготовлений і затверджений автором26.10.2026 еталон; записи/докази в review ledger.

Enum/bool — exact; списки — exact set accuracy плюс micro TP/FP/FN/P/R/F1, без aliases/fuzzy. Порядок не впливає, 0 denominator → null. Всі G залишаються у per-field denominator, missing/invalid прогнози не дорівнюють false/[]; aggregate=correct/(8G), content=correct без language/(7G), language окремо. Runtime на golden_10 має відомі n, observed A_G, V_G/A_G і V_G/G, coverage. Baseline all_30 окремий. Latency p50/p95 — лінійна інтерполяція (n−1)q на відомих pipeline latency, включає записані retry/repair. Cold start unknown, не вигаданий benchmark.

Usage спільний з v1: HTTP requests не дублюються з attempt.usage; unknown cost=null, локальна external API=0 не означає нуль витрат обладнання. `--pricing` читає датований локальний тариф. `results/schema_v2/pricing.json` — поточний тариф для планування; фактичний returned_model треба звірити перед фінальним розрахунком. Summary містить hashes входів і версію evaluator policy. Output новий/порожній, summary записується останнім; code 0=повний технічний coverage, 1=partial, 2=помилка. Provisional статус не означає готові фінальні accuracy.

## Експеримент і ручні gates

8 конфігурацій N=30/30/10/10/10/10/10/10, разом120. G=10 однакова для порівнянь; D=4 non-golden ID у development_notes, D∩G=∅. Prompt-v2 створюється тільки після реального baseline аналізу D й заморожується до порівняння на G; golden feedback не використовується для tuning. Історичний доступ до G у v1/evaluator розкрито як обмеження незалежності.

[Ручний review](../data/golden_v2_review.md) вимагає перевірки всіх8 полів кожного з10 джерел і reviewer/date; агент не затверджує себе. Golden freeze потрібен для фінальних оцінок, але не technical probes/baseline. Paid probes/batch потребують конкретного залишкового бюджету до $5 після кошторису; локальна модель не завантажується автоматично. Ці gates виконані: реальні v2 results, final REPORT і production-рекомендація з авторським погодженням збережені. Optional240/resume/cold не блокують mandatory120.

Coverage основної матриці без API: `python -m src.evaluation_v2.matrix`. Код1 означає missing primary (зараз120/120, код0), не падіння моделі. План і hashes перевіряються перед підрахунком.

## Фактичне приймання26.10.2026

10/10 golden approved,4 probes accepted,120/120 primary у8 наборах30/30/10/10/10/10/10/10; failed збережені й входять у знаменники. Два промпти й T0/T07 не підмінені. Prompt-v2 не покращив GPT content accuracy (62/70 у всіх4 випадках); подробиці, мінуси recall та умовна погоджена конфігурація — REPORT.md. Усі8 strict evaluations відтворюються без API.
