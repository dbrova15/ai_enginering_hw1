# План Schema v2: 120 primary attempts

Статус:120/120 primary attempts завершені,4 probes успішні; бюджет$4.95 погоджено користувачем26.10.2026. Налаштування .env не змінені.

| ID | Provider/model | Prompt | T/top_p | N | Статус |
| --- | --- | --- | --- | --- | --- |
| GPT-v1-T0 | openai/gpt-4o-mini | schema_v2/v1 | 0/1 | 30 | not_started |
| OSS-v1-T0 | ollama/llama3.2:3b | schema_v2/v1 | 0/1 | 30 | not_started |
| GPT-v1-T07 | openai/gpt-4o-mini | schema_v2/v1 | 0.7/1 | 10 | not_started |
| OSS-v1-T07 | ollama/llama3.2:3b | schema_v2/v1 | 0.7/1 | 10 | not_started |
| GPT-v2-T0 | openai/gpt-4o-mini | schema_v2/v2 | 0/1 | 10 | not_started |
| OSS-v2-T0 | ollama/llama3.2:3b | schema_v2/v2 | 0/1 | 10 | not_started |
| GPT-v2-T07 | openai/gpt-4o-mini | schema_v2/v2 | 0.7/1 | 10 | not_started |
| OSS-v2-T07 | ollama/llama3.2:3b | schema_v2/v2 | 0.7/1 | 10 | not_started |

Сума N=120. Ще мінімум 4 probes: 2 моделі × 2 sampling, окремо від primary.

Кошторис 26.10.2026: $0.15/M input, $0.60/M output, за [офіційною документацією](https://developers.openai.com/api/docs/models/gpt-4o-mini). Груба консервативна оцінка 62 платних генерацій без retry/repair: до $0.592; із максимум 6 HTTP на документ: до $3.551. Це планова byte-оцінка, не гарантія білінгу. Повторні probes та збільшення prompt-v2 потребують перерахунку. Повні числа/припущення — budget.json.

Попередні реальні витрати та залишок $5 невідомі: користувач підтвердив конкретний доступний залишок$4.95; витрати заusage у budget_ledger.json. Локальні 60 primary + 2 probes не мають зовнішньої API-плати; обладнання/електрика не оцінені.

Команди кожного рядка збережені в plan.json → cli_argv. Перед командою тимчасово задати process LLM_PROVIDER/OPENAI_MODEL або OLLAMA_MODEL відповідно рядку; .env не переписувати. Не запускати всі команди автоматично до probes.

Freeze підготовки: schema-v2-text-v1; source/input hashes для 30 ID у plan.json. Цей freeze не є freeze неперевірених golden labels. Prompt v2 null до аналізу реального D; не дублювати перші 60 запусків.

Фактичний статус кожного набору та prompt-v2 hashes оновлено в plan.json; matrix_status.json підтверджує120/120 і missing0. Первинні умовні формулювання вище описують gates до запуску, не поточну незавершеність.
