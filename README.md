# HardwareResearch AI

## Schema v2 — перевірений конвеєр і результати120

Основна демонстраційна команда після налаштування активного провайдера:

```powershell
.\.venv\Scripts\python.exe main.py --schema-version v2 --document data/sourses/hm1/texts/uk/HR-0187.txt
```

Без `--prompt` вона обирає `prompts/schema_v2/v1.txt`, ізольований новий каталог `results/schema_v2/baseline/<uuid>` та сувору Schema v2. Без `--schema-version` збережено попередню поведінку v1. Реальна демонстрація викликає модель; хмарні запуски виконувати тільки в погодженому бюджеті.

```powershell
# Усі 30 документів, T0:
.\.venv\Scripts\python.exe main.py --schema-version v2 --all-documents --temperature 0 --top-p 1 --output-dir results/schema_v2/NEW-EXPERIMENT
# Рівно 10 еталонних ID, T07:
.\.venv\Scripts\python.exe main.py --schema-version v2 --document-ids data/sourses/hm1/golden_v2_ids.txt --temperature 0.7 --top-p 1 --output-dir results/schema_v2/ANOTHER-EXPERIMENT
# Лише збережені результати, без API та .env; каталог NEW-EVALUATION має бути новим:
.\.venv\Scripts\python.exe evaluate_v2.py --golden data/sourses/hm1/golden_v2.json --runs results/schema_v2/NEW-EXPERIMENT --output-dir results/schema_v2/NEW-EVALUATION
```

`--temperature` та `--top-p` замінюють тільки явно задані значення Settings; `0` має пріоритет над config `0.7`. Допустимі скінченні temperature `[0,2]`, top_p `(0,1]`; без аргументів діє `.env`. ID-файл містить тільки ID, по одному на рядок; unknown/duplicate/empty відхиляються до HTTP. Каталоги v1/непорожні outputs захищені. Для approved-еталона додати evaluator `--strict-golden`; поточні10 еталонів вручну approved і приймаються у strict.

План **120 primary** (2×30 baseline + 6×10), hashes, D/G і кошторис: [plan.md](results/schema_v2/plan.md), [plan.json](results/schema_v2/plan.json). Виконано120/120 primary у8 конфігураціях і4 успішні реальні probes2×2. Prompt-v2 зафіксовано за помилками3 non-golden текстів D до оцінювання G, D∩G=∅. Попереднє використання G у v1/evaluator обмежує незалежність фінального тесту.

[Контракт, підготовка тексту та метрики](docs/SCHEMA_V2.md). [Затверджені людські рішення](data/golden_v2_review.md). Якість рахується на G=10: content 7G=70, aggregate 8G=80, незалежно від N=30 чи N=10. Runtime golden_10 порівнюється окремо від baseline_all_30. Версії й hashes schema/prompt/source/prepared input записані в кожному новому v2 run; старі TXT/v1 не змінюються.


Скрипт витягує дані з **однієї TXT-статті або всіх TXT корпусу** через OpenRouter, прямий OpenAI API або локальну Ollama, перевіряє JSON погодженою Pydantic-схемою та зберігає звіти. Потрібні Python 3.11+ та модель; для хмарних сервісів — ключ активного сервісу.

## Підготовка

У PowerShell із кореня проєкту, де вже є `.venv`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Якщо середовища ще немає, спочатку створіть його встановленим Python 3.11+: `python -m venv .venv`.

Скопіюйте `.env.example` у `.env`, якщо приватний файл ще не створений, і заповніть:

```dotenv
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=ваш_приватний_ключ
OPENROUTER_MODEL=ID_обраної_моделі
```

Для прямого OpenAI API:

```dotenv
LLM_PROVIDER=openai
OPENAI_API_KEY=ваш_приватний_ключ_OpenAI
OPENAI_MODEL=ID_моделі_OpenAI
```

`LLM_PROVIDER` приймає `openrouter`, `openai` або `ollama`. Якщо змінна відсутня, порожня або містить лише пробіли, активним є **OpenRouter**: попередній `.env` залишається сумісним. Регістр і пробіли навколо значення ігноруються. Невідомий selector спричиняє локальну помилку.

Заповнюйте тільки ключ і модель активного сервісу; налаштування неактивного не потрібні. При `openai` відсутність `OPENAI_API_KEY` чи `OPENAI_MODEL` не підміняється значеннями OpenRouter і не перемикає провайдера автоматично. Приватний `.env` скрипт не редагує.

## Локальна модель Ollama

Встановіть [Ollama](https://ollama.com/download), запустіть застосунок або сервер `ollama serve` і попередньо завантажте саме обрану модель:

```powershell
ollama pull llama3.2:3b
```

У `.env` виберіть:

```dotenv
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2:3b
OLLAMA_BASE_URL=http://localhost:11434
```

API-ключ для локального маршруту не потрібний. Якщо OLLAMA_MODEL або OLLAMA_BASE_URL відсутні чи порожні, використовуються наведені типові значення. Адреса повинна містити лише HTTP(S)-схему, хост і необов'язковий порт, без шляху, credentials, query та fragment. Клієнт сам додає `/v1/chat/completions`. Налаштування та ключі хмарних сервісів у цьому режимі ігноруються; `Authorization` не передається.

Адаптер використовує [сумісний HTTP-інтерфейс Ollama](https://github.com/ollama/ollama/blob/main/docs/api/openai-compatibility.mdx): JSON Schema, temperature, top_p та max_tokens. Підтримку `response_format.type=json_schema` можна звірити з [перетворенням запиту в коді Ollama](https://github.com/ollama/ollama/blob/main/openai/openai.go). Залишаються локальна Pydantic-валідація й одна repair-спроба. Додатковий Python SDK не потрібний.

Запуск той самий: `python main.py`. Якщо модель не завантажена або сервер не працює, запит завершується `failed` зі збереженим звітом; програма не встановлює Ollama, не завантажує модель і не перемикається на платний API автоматично.

Перше звернення може довше завантажувати модель у пам'ять. За потреби збільшіть спільний REQUEST_TIMEOUT_SECONDS, наприклад до 180. Для майбутніх замірів вимірюйте cold start окремо від прогрітих запусків. У поточному звіті загальний latency включає це завантаження, якщо воно сталося; окремої метрики cold start ще немає. Якість Schema v2 на llama3.2:3b вже перевірено реальними прогонами на approved golden; див. REPORT.md. Локальних API-платежів немає, але витрати ресурсів комп'ютера не вимірюються.

## Спільні налаштування та відмінності API

Не використовуйте наведені пояснювальні значення як справжні параметри. ID моделі та API-ключ — різні речі. `.env` ігнорується Git. Змінні процесу мають пріоритет над `.env`; інші налаштування наведені в `.env.example`.

Модель і конкретний endpoint мають підтримувати JSON Schema та задані параметри семплінгу. Усі клієнти надсилають `response_format.type=json_schema` та `strict=true`; локальна перевірка Pydantic залишається обов'язковою незалежно від реалізації constrained output сервером. OpenRouter також отримує `provider.require_parameters=true` та `max_tokens`. Див. [документацію structured output OpenRouter](https://openrouter.ai/docs/guides/features/structured-outputs).

OpenAI-клієнт надсилає запити на `https://api.openai.com/v1/chat/completions` зі спільним лімітом `MAX_TOKENS` у полі `max_completion_tokens`, без параметрів маршрутизації OpenRouter. Цей ліміт у Chat Completions включає також reasoning-токени. Див. [офіційну документацію OpenAI API](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) та [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs). `temperature` і `top_p` передаються явно; для моделей, які їх не підтримують, API поверне помилку — скрипт не змінює sampling приховано.

## Запуск

```powershell
.\.venv\Scripts\python.exe main.py
```

Типово обробляється короткий текст `HR-0187` про автополив. Після активації середовища той самий запуск — `python main.py`.

Щоб вибрати іншу статтю:

```powershell
.\.venv\Scripts\python.exe main.py --document data/sourses/hm1/texts/en/HR-0743.txt
```

Доступні також `--prompt` і `--output-dir`. Підказка `python main.py --help` не викликає API. Власні відносні шляхи рахуються від поточного каталогу; типові — від кореня проєкту.

Щоб обробити всі TXT у `data/sourses/hm1/texts/` разом із підкаталогами `en/`, `ru/`, `uk/`:

```powershell
.\.venv\Scripts\python.exe main.py --all-documents
```

Для іншого промпту або окремого каталогу результатів:

```powershell
.\.venv\Scripts\python.exe main.py --all-documents --prompt prompts/v1.txt --output-dir results/batch_v1
```

`--all-documents` і `--document` взаємовиключні. Коли жоден не заданий, зберігається одиночний запуск HR-0187. У пакетному режимі програма сортує файли за відносними шляхами, перевіряє всі тексти й промпт до першого API-запиту та обробляє кожну статтю окремо. Не-TXT файли ігноруються. Провайдер, sampling та інші налаштування читаються один раз на початку прогону.

Кожен документ отримує власний `run_<uuid>.json`. Консоль показує `[номер/всього]`, шлях звіту та підсумок `success`, `repaired`, `failed`, `не оброблено`. При невалідній відповіді чи HTTP 400 окремої статті черга продовжується. Помилки доступу/балансу, відсутній endpoint чи модель (401/402/403/404), вичерпаний timeout/rate limit (408/429), 5xx або мережевий збій після retry зупиняють чергу; уже записані результати зберігаються. Помилка локального читання чи запису завершує запуск кодом 2.

Пакетний режим **не пропускає вже наявні результати**: кожен явний запуск повторно обробляє весь корпус, створюючи нові файли. Для різних моделей, промптів або sampling-конфігурацій зручно задавати окремий `--output-dir`.

**Запуск із налаштованою моделлю робить реальні запити; хмарні сервіси можуть витрачати кошти, а Ollama використовує локальні ресурси.** MAX_TOKENS обмежує одну відповідь, але не встановлює доларовий бюджет. `--all-documents` може зробити до 30 генерацій із додатковими retry/repair; окремого грошового обмежувача та автоматичної оцінки вартості в CLI немає.

## Що відбувається із запитом

1. Конфігурація та непорожні UTF-8-файли перевіряються до API-виклику.
2. Незмінений `prompts/v1.txt` передається як system, стаття — як user; golden set і правильні мітки маніфесту не передаються.
3. Схема задає вісім полів, два enum та вкладені компоненти/параметри. Всі ключі обов'язкові, невідомі nullable-значення — `null`, порожні списки — `[]`.
4. Мережеві збої, timeout, HTTP 408/429/5xx мають обмежені retry. При 400/401/402/403 повторів немає. Пауза зростає; враховується `Retry-After`. Якщо сервер вимагає чекати довше MAX_RETRY_WAIT_SECONDS, запуск завершується помилкою без передчасного повтору. Див. [помилки OpenRouter](https://openrouter.ai/docs/api_reference/errors-and-debugging).
5. Невалідний JSON або структура отримують **одну спробу repair**: моделі повертається попередня відповідь з описом помилок. Відмова, обрив генерації чи помилка API завершуються `failed` без repair. Після другої невалідної відповіді — теж `failed`.

Timeout httpx обмежує очікування окремих мережевих операцій, а не тривалість усього запуску. За MAX_RETRIES=2 дозволено до 3 HTTP-спроб на генерацію; із repair — до 6. Після timeout сервер міг уже виконати запит, тому повтор може додатково оплачуватися.

## Результати

Кожен запуск створює новий `results/run_<uuid>.json`, зберігаючи попередні файли. У ньому є:

- `result` — перевірений об'єкт із вісьмома полями або `null`;
- `status` — `success`, `repaired` або `failed`; `first_pass_valid` окремо показує валідність початкової генерації;
- ID документа, активний `provider`, запитана модель, версія/хеш промпту, sampling і ліміти;
- `attempts` — початкова генерація та, за наявності, repair: повернена модель, usage, сирий вміст, finish_reason, помилка й усі HTTP-спроби;
- `retry_count` — кількість додаткових HTTP-спроб, без урахування самої repair-генерації;
- UTC-час та `latency_seconds` усього конвеєра до запису файла, включно з HTTP-повторами, паузами, перевіркою й repair; кожен HTTP-запит має власну тривалість.

Невідомий usage залишається `null`, не нулем. Ключ маскується навіть у сирому віддзеркаленні сервера. Відповіді можуть повторювати текст статті, тому перед публікацією результатів перегляньте їхній вміст.

Код завершення: `0` — всі вибрані документи успішні або виправлені repair; `1` — є невдалий API/витягування чи необроблена решта після зупинки сервісу; `2` — помилка конфігурації, аргументів, локальних файлів чи запису на диск.

## Перевірки без мережі

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Тести підміняють HTTP через MockTransport і не використовують ваш ключ. Перевіряються схема, конфігурація, retry, repair, формат відповіді, CLI та збереження без секретів.

## Організація коду та межі

`main.py` читає аргументи й координує запуск; `src/document_runner.py` готує документи, обробляє їх послідовно та формує метадані й підсумок. `src/schema.py` описує дані; `src/config.py` перевіряє налаштування; `src/client_factory.py` вибирає активний клієнт; `src/chat_client.py` виконує спільні HTTP/retry. `src/openrouter_client.py`, `src/openai_client.py` та `src/ollama_client.py` задають адресу й параметри свого API; `src/extraction.py` перевіряє відповіді й керує repair; `src/result_writer.py` записує звіт. Класи й функції пояснені українськими docstring, які доступні також через `help()`.

25.10.2026 baseline v1 прогнано на всіх 30 текстах моделлю GPT-4o mini: 29 документів через прямий OpenAI API та один попередній — через OpenRouter. Усі 30 відповідей отримали HTTP 200 й пройшли Pydantic з першої спроби; retry/repair не знадобилися. Історичний summary `results/baseline_v1_2026-10-25_summary.json` зараз відсутній у дереві; доступні [сирі v1 результати](results/step1). У попередньому записі зафіксовано usage та оцінку вартості28 нових запитів — $0.03374880 за тарифом без знижки на кеш; це не підтвердження суми рахунку. Попередні два результати збережено без повторного виклику.

Цей baseline-прогін виконано послідовними одиночними запусками до появи `--all-documents`; новий пакетний режим перевірено офлайновими тестами без повторного оплачуваного прогону. Поточні збережені результати провайдерської та локальної моделей містяться в `results/step1` та `results/step2`; оцінювач читає саме файли, а не історичний summary. Чернетки `golden.json` потребують ручної перевірки.

## Офлайнове оцінювання Golden Set

```powershell
.\.venv\Scripts\python.exe evaluate.py --golden data/sourses/hm1/golden.json --runs results/step1 results/step2 --output-dir results/evaluation
```

Команда не викликає LLM і не читає `.env`. Вона створює `summary.json`, `details.json`, `comparison.md`; output має бути новим або порожнім каталогом. Для повторного запуску задайте інший `--output-dir`.

Історичні10 еталонів **Schema v1** мають `needs_human_review`, тому саме v1 оцінювання **provisional**. Окремий golden_v2 уже approved. `--strict-golden` допускає лише `annotation_status=approved` і зараз очікувано відхиляє запуск. Статуси не змінюються автоматично. Оцінюються всі вісім полів, компоненти та параметри зіставляються один до одного, `needs_review` не зараховується як правильний факт.

Точна відповідність формулюванням/атрибутам не є семантичною точністю; обмежений словник aliases може не розпізнати правильне перефразування. Вартість без достовірного API cost або явно переданого `--pricing` лишається невідомою. Cold start не вгадується з першого запиту. Коди завершення: 0 — технічно повний звіт, 1 — звіт із missing/failed/invalid, 2 — фатальні входи/strict refusal/запис.

[Методика, формули, aliases, тарифи, формати й обмеження](docs/EVALUATION.md). [Порівняльний звіт](results/evaluation/comparison.md).

Оновлена політика `golden-evaluator-v2.0` розпізнає підтверджені міжмовні технічні поняття, одиниці й розміри. Непідтверджений subject лишається `needs_review`, а неправильні атрибути не дають full_fact TP. Нові результати не замінюють старих: [звіт v2](results/evaluation-semantic-v2/comparison.md), [порівняння evaluator до/після](results/evaluation-semantic-v2/before_after.md). Методика відтворення та `compare_evaluators.py` описані в [документації](docs/EVALUATION.md#відтворення-допісля).

## Результат Schema v2 і рекомендований запуск

[REPORT.md](REPORT.md) містить8 конфігурацій, якість на G=10, latency/cost,5 реальних помилок і погоджену автором умовну production-рекомендацію. Для індексації з пріоритетом точності тегів: **OpenAI gpt-4o-mini, Schema v2, prompt schema_v2/v1, temperature=0, top_p=1**. Content62/70, JSON validity100%; recall інтерфейсів лише3/7 — це суттєве обмеження, а не гарантія повноти.

```powershell
# Викликає модель; API key уже має бути у приватному .env або оточенні:
$env:LLM_PROVIDER = 'openai'
$env:OPENAI_MODEL = 'gpt-4o-mini'
.\.venv\Scripts\python.exe main.py --schema-version v2 --document data/sourses/hm1/texts/uk/HR-0187.txt --temperature 0 --top-p 1
# Повне offline відтворення на збережених120, без API/читання .env:
.\.venv\Scripts\python.exe evaluate_v2.py --golden data/sourses/hm1/golden_v2.json --runs results/schema_v2/GPT-v1-T0 results/schema_v2/OSS-v1-T0 results/schema_v2/GPT-v1-T07 results/schema_v2/OSS-v1-T07 results/schema_v2/GPT-v2-T0 results/schema_v2/OSS-v2-T0 results/schema_v2/GPT-v2-T07 results/schema_v2/OSS-v2-T07 --output-dir results/schema_v2/NEW-EVALUATION --strict-golden --pricing results/schema_v2/pricing-final.json
.\.venv\Scripts\python.exe -m src.evaluation_v2.matrix
```

Змінні вище діють у поточному PowerShell; файл .env не переписується. Повторний paid demo лише заради документації не потрібен: реальні результати вже збережені, demo smoke перевірений MockTransport. Output для evaluation має бути новим/порожнім. Метрики й hashes: [evaluation-final](results/schema_v2/evaluation-final/summary.json); витрати: [budget ledger](results/schema_v2/budget_ledger.json).
