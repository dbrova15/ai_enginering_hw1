# Порівняння поточного prompt-v3: OpenAI та Ollama

Дата:26.10.2026. Виконано **60/60 нових primary attempts**, по30 на кожній моделі. Попередні результати не змінені.

Prompt SHA-256: `f45f5854945d838277869421bed26a8cc1480082c5a7628c71896e9f3a439f7e`. Заморожена копія — [v3.txt](v3.txt). Поточний файл на початку збігався з попереднім Ollama v3: це новий повторний експеримент, а не доказ зміни тексту промпту. Schema v2; temperature=0,top_p=1, max_tokens4096, max_retries2. Провайдер обирався лише через process env; .env не переписувався.

Якість — на одному approved golden set G=10; content без мови=correct/70, aggregate=correct/80. Невалідні/failed лишаються у знаменниках. Validity/latency/usage/cost нижче — на всіх30 документах кожного провайдера; ці знаменники не змішані.

| Модель | Success / repaired / failed (30) | JSON first → final | Content (G10) | Aggregate (G10) | p50 / p95, с (N30) | External API $/1000 |
| --- | --- | --- | --- | --- | --- | --- |
| gpt-4o-mini | 29 / 0 / 1 | 29/30 → 29/30 | 62/70 (88.57%) | 72/80 (90.00%) | 1.609 / 2.632 | 0.3810 |
| llama3.2:3b | 16 / 4 / 10 | 16/30 → 20/30 | 28/70 (40.00%) | 31/80 (38.75%) | 3.356 / 29.173 | 0; hardware unknown |

## Точність полів — кожне /10

| Поле | GPT-4o mini | Llama3.2:3b |
| --- | --- | --- |
| language | 10/10 | 3/10 |
| primary_topic | 10/10 | 2/10 |
| mentioned_platforms | 9/10 | 4/10 |
| mentioned_interfaces | 6/10 | 1/10 |
| mentions_sensor | 9/10 | 6/10 |
| mentions_display | 9/10 | 5/10 |
| mentions_battery | 10/10 | 5/10 |
| mentions_motor | 9/10 | 5/10 |

## Списки — micro метрики на G10

| Модель / поле | TP / FP / FN | Precision | Recall | F1 |
| --- | --- | --- | --- | --- |
| gpt-4o-mini / mentioned_platforms | 9 / 0 / 1 | 1.000 | 0.900 | 0.947 |
| gpt-4o-mini / mentioned_interfaces | 3 / 1 / 4 | 0.750 | 0.429 | 0.545 |
| llama3.2:3b / mentioned_platforms | 6 / 3 / 4 | 0.667 | 0.600 | 0.632 |
| llama3.2:3b / mentioned_interfaces | 3 / 11 / 4 | 0.214 | 0.429 | 0.286 |

## Невдалі відповіді

- openai: {'duplicates_after_repair': 1}. HR-0640 (duplicates_after_repair).
- ollama: {'length': 4, 'duplicates_after_repair': 6}. HR-0743 (length); HR-0245 (duplicates_after_repair); HR-0164 (length); HR-0640 (length); HR-0982 (duplicates_after_repair); HR-0254 (duplicates_after_repair); HR-0415 (duplicates_after_repair); HR-0773 (length); HR-0055 (duplicates_after_repair); HR-0297 (duplicates_after_repair).

GPT HR-0640 залишив три arduino в mentioned_platforms у першій генерації й після repair. У Ollama6 дублікатів після repair та4 length на4096токенах. Збільшення token limit не усуває дублікати. Failed primary не повторювались для заміни кращою відповіддю.

## Runtime і витрати

Запуски моделей виконувалися паралельно. Latency — pipeline wall time із retry/repair, p50/p95 лінійні(n−1)q; known n=30 для кожної моделі. Cold start=unknown; контрольованого cold benchmark немає. Валідність JSON не є factual accuracy.

- gpt-4o-mini: tokens input/output=82451/2231; HTTP requests=31; на G valid=10/10.
- llama3.2:3b: tokens input/output=73751/19135; HTTP requests=40; на G valid=7/10.

Нові OpenAI витрати за фактичним token/cache usage і датованим тарифом: **$0.01143105**; розрахунковий залишок раніше погодженого ліміту після цього експерименту **$4.91895150**, без урахування сторонніх ручних витрат. Джерело тарифів — pricing.json з official source/date; $/1000 — екстраполяція того самого cache/token mix, не billing statement. Для локальної моделі external API=0, hardware/electricity cost unknown.

## Висновок та обмеження

На цій підвибірці GPT має вищі factual accuracy/validity і нижчу pipeline latency, ніж Llama. Content GPT62/70 збігається з попередніми v1/v2/T0 результатами; збільшення aggregate якості від v3 тут не виміряно. Усі спостереження — один повторний прогін на10 вже відомих еталонах, не сліпий тест і не доказ статистичної значущості. Налаштований T0 сам по собі не гарантує повторюваності всіх відповідей.

[Повні strict метрики](evaluation/summary.json), [помилки по полях](evaluation/details.json), [budget ledger](budget_ledger.json). Джерела/input hashes та prompt hash перевірені, IDs30/30 у кожній моделі, schema валідність успішних результатів підтверджена. Git-коміт не створювався.
