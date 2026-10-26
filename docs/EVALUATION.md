# Golden Set Evaluator v1

Оцінювач працює повністю офлайново: читає збережені JSON, не завантажує `.env`, не викликає LLM та не змінює входи. Встановлених залежностей проєкту достатньо; окремий CLI не змінює `main.py`.

## Запуск

```powershell
.\.venv\Scripts\python.exe evaluate.py --golden data/sourses/hm1/golden.json --runs results/step1 results/step2 --output-dir results/evaluation
```

Output має бути новим або порожнім каталогом і не може перетинатися з runs чи містити захищені входи. Для наступного оцінювання вкажіть, наприклад, `--output-dir results/evaluation-next`. Попередні результати не перезаписуються. З кожного runs-каталогу читаються лише `run_*.json` без рекурсії; старі summary/Markdown не використовуються як виміри.

За замовчуванням використовуються `data/sourses/hm1/manifest.json` та `data/golden_annotation_rules_v1.md`. Можна передати інші шляхи через `--manifest`, `--annotation-rules`.

```powershell
.\.venv\Scripts\python.exe evaluate.py --golden data/sourses/hm1/golden.json --runs results/step1 results/step2 --output-dir results/evaluation-approved --strict-golden
```

Strict допускає тільки `annotation_status = approved`. Поточні 10 записів мають `needs_human_review`, тому звичайний запуск позначається `Evaluation status: provisional (golden labels not fully approved)`, а strict відхиляється без створення виходів. Оцінювач не змінює статусів автоматично. Затвердження — окрема ручна процедура звірки з TXT.

Коди завершення: **0** — технічно повне покриття й придатні результати (не гарантія високої якості); **1** — звіти створені, але є missing/failed/невалідні прогнози чи конфлікти метаданих; **2** — фатальні входи, дублікати, strict refusal або помилка запису. Provisional і needs_review самі по собі не змінюють 0 на 1.

## Ідентичність експерименту

Групування враховує provider, requested/returned model, версію й SHA-256 промпту, sampling, schema version та limits. Snapshot не підміняється запитаною моделлю. Відсутні snapshot/limits явно залишаються unknown. Два файли одного document_id в одній групі — помилка, а не вибір останнього чи найкращого. Повтор одного каталогу враховується один раз із діагностикою.

OpenAI/OpenRouter можуть бути маршрутами тієї самої моделі; evaluator їх приховано не об’єднує і не називає різними моделями лише через provider. Новий prompt hash або sampling створює окрему конфігурацію. Для оцінки регресій потрібно зберігати той самий golden hash і policy hash; якщо змінилися правила оцінювання — переоцінити обидві сторони.

Provenance містить хеші golden, manifest, правил, джерел, runs, policy й реалізації, версії Python/Pydantic та CLI. Порядок записів стабільний; generated_at та output path можуть відрізнятися. Після обчислення перевіряється, що входи не змінилися під час запуску.

## Порівняння полів

`result` перевіряється чинною Pydantic-схемою. `raw_content` не використовується для відновлення або покращення результату. Failed із ненульовим result, success із невалідним result та неузгоджені дані спроб мають явні діагностики.

- `document_type`, `primary_topic`: точний enum match.
- `main_subject`, `purpose`: NFC, регістр, пробіли, апострофи й зовнішня незначуща пунктуація. Перефразування без явного alias → needs_review. Переклад або string similarity не дає автоматичного TP.
- `components`: one-to-one зіставлення за назвою/alias або явною моделлю. Identity PR/F1 відокремлено від full_fact PR/F1. Для повного збігу перевіряються name/model/manufacturer/role. `R1`, `C1`, `K1` не є моделями; model=null не дозволяє вгадувати модель.
- `technical_parameters`: subject і назва характеристики визначають кандидатів; числа для різних пристроїв не утворюють пару. Повний факт потребує правильних subject/name/value/unit і статусу desired/measured/declared/nominal/example/typical. Відсутній потрібний контекст → needs_review; суперечливий → mismatch.
- `interfaces_protocols`, `software_tools`: окремі множини з незалежними namespaces aliases. Значення з одного поля не закриває пропуск в іншому. Рядкові дублікати діагностуються, але не додають TP.

Явні aliases зберігаються в `src/evaluation/policy.py`: наприклад, UNO/Uno через casefold, I²C/I2C, Wifi/Wi-Fi, relay/реле. Словник обмежений і спільний для моделей; це не універсальний перекладач. Немає нечіткого порога або автоматичного розширення aliases за відповідями однієї моделі.

Для object lists застосовується глобальне min-cost flow: спочатку максимальна кількість допустимих пар, потім максимальна сума рівнів доказу. Перерахунок із забороною ребра визначає, чи є пара обов’язковою в усіх оптимумах. Рівноцінні альтернативи лишаються review-групою; порядок масиву не обирає правильну відповідь. Однакові дублікати групуються з кратністю: одна копія прогнозу може бути TP, решта — extras; дублікати golden сигналізують проблему еталона й provisional.

## Числові величини

Використовується Decimal без довільної tolerance. Підтримуються десяткова кома/крапка, від’ємні значення, діапазони, `<`, `<=`, `>`, `>=`, приблизність та явні фрази `under`, `at least`, `щонайменше`, `приблизно`, `a dozen`. `<100` не дорівнює `100`, desired не дорівнює measured.

Підтримувані позначення й еквівалентні одиниці перелічено в `quantities.py`: зокрема V/В/volts, uA/µA/μA/microamperes, A/mA, F/mF/uF, kg/g, m/cm/mm, s/ms/h. SI-регістр зберігається: mF і uF — різні масштаби. Перерахунок допускається лише для відомої розмірності. Одиниця всередині value має узгоджуватися з unit; суперечність не виправляється мовчки.

Невідомі конфігурації, наприклад A4 або 3x2, можуть точно збігатися як opaque текст. Незрозуміле перефразування чи неоднозначне `1,234` не інтерпретується довільно. За відсутності розпізнаного alias/контексту правильний факт може не отримати автоматичного TP.

Для HR-0207 registry документує конфлікт lm7508/lm7805, прив’язаний до SHA-256 TXT. Обидва написання потребують перегляду і не перетворюються на aliases. При зміні fingerprint registry стає непридатним. Джерело та еталон не виправляються.

## Формули й знаменники

G — усі golden документи; A — усі унікальні runs групи, включно з failed. Coverage = present golden runs/G. Runtime рахується на A, якість — на G. Missing/невалідний прогноз не дає exact навіть для порожнього еталонного поля; expected об’єкти залишаються FN, невідомі predicted FP не вигадуються.

Field exact = повністю правильні поля/G. Для object list потрібні всі елементи й атрибути без extra/review, для string list — рівність canonical множин. Aggregate exact = сума exact восьми полів/(8G). Це сувора відповідність поточному еталону, а не універсальна семантична accuracy.

Micro P=TP/(TP+FP), R=TP/(TP+FN), F1=2TP/(2TP+FP+FN). Строгий full_fact із невідомим атрибутом не є TP і консервативно дає FP+FN; identity сутності при цьому може бути правильною. Нульовий знаменник → null. Порожні правильні списки дають exact, але не штучний micro PR=100%.

Review accounting має атомарні check IDs: scalar/атрибут, membership рядкового елемента або неоднозначна identity-група. `needs_review/total_checks`, auto_decided, unavailable, review_documents/G та кількість pairing-груп наводяться окремо. Сума verdict counts дорівнює total_checks. Це показник ручної роботи, а не додаткова accuracy.

`missing`/`extra_predicted` у details позначають незакриті елементи; атрибутна помилка вже зіставленого компонента описується в pair checks і full_fact FP/FN. **Extra не є доведеною галюцинацією**: еталон теж може бути неповним.

## Latency, usage та вартість

p50/p95 — лінійна інтерполяція `(n−1)q` відомих невід’ємних `latency_seconds` усіх runs. Це час конвеєра з відображеними retry/repair. Unknown latency не дорівнює нулю. Перший запит автоматично не називається cold start і не виключається. Для відокремлення потрібен новий контрольований вимір; evaluator його не виконує.

Usage враховується по кожному HTTP request усіх генерацій. Копії у response/attempt не додаються двічі. Fallback attempt.usage дозволено лише для єдиного request. Mean input/output рахується для документів із повними відомими даними; окремо наводяться known_sum, known/unknown request counts. Неуспішний request без usage не стає нульовим.

Без тарифного файла evaluator використовує тільки відоме API `usage.cost`. За відсутності cost/тарифу ціна = null, а не вигадана оцінка. Локальний зовнішній API-тариф = 0; повна вартість обладнання/електроенергії невідома.

Необов’язковий `--pricing path/to/pricing.json` приймає масив із полями:

| Ключ | Тип / правило |
| --- | --- |
| provider, requested_model | Точні рядки з групи |
| returned_model | Точний snapshot або null для групи unknown |
| currency | USD |
| as_of | YYYY-MM-DD |
| source_url | HTTP(S) URL джерела тарифу |
| input_per_million, output_per_million | Невід’ємні числа |
| cached_input_per_million | Необов’язкове число; за наявності потрібен відомий cached usage |

Довільний приклад для синтетичної моделі (це не ціни реального постачальника):

```json
[{"provider":"test","requested_model":"test-model","returned_model":"test-model-v1","currency":"USD","as_of":"2026-10-25","source_url":"https://example.org/pricing","input_per_million":2,"cached_input_per_million":1,"output_per_million":4}]
```

Cost = `((input−cached)×input_rate + cached×cached_rate + output×output_rate)/1000000`. Без cached-тарифу використовується явно позначене припущення uncached. API-reported cost має пріоритет. Повний cost/1000 = mean повної вартості документа ×1000; partial_known_cost та priced/total requests відображаються окремо. Не можна екстраполювати неповну суму як повну вартість. Джерела/дати тарифів включаються у звіт, мережевої перевірки під час оцінки немає.

## Вихідні файли та достовірність

- `summary.json`: конфігурації, provenance, coverage, точність восьми полів, PR/F1, review, runtime/usage/cost та їхні бази/знаменники. Для нечасток numerator/denominator не застосовуються; метод і sample/known counts описують вимір.
- `details.json`: документ → поле → оригінальні/canonical значення, індекси, checks, reason/rule IDs, matching, missing/extra/review. Scoped check ID містить group/document. Не дублює raw HTTP-тексти.
- `comparison.md`: українські таблиці, приклади обох конфігурацій, факти та обмеження, шість підрозділів фінального висновку. `summary.json` публікується останнім як маркер завершення; при помилці запису не слід використовувати частковий каталог як готовий звіт.

Низький strict score або нуль full_fact TP може відображати обмеження aliases/перекладів і перефразувань, а не відсутність правильних фактів. Provisional-еталони та лише 10 документів не дозволяють впевнено обрати production-переможця. Кількість об’єктів не дорівнює кількості незалежних спостережень. Статистична значущість не обчислюється.

Офлайнові перевірки:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Тести включають межі, одиниці, null, контекст, перестановки, дублікати, matching проти повного перебору малих графів, строгий режим, partial usage/cost, детермінізм, незмінність входів і відсутність читання `.env`/мережі.

## Семантична політика v2

`golden-evaluator-v2.0` розширює підтверджені еквівалентності, не змінюючи golden, Schema v1 або результати моделей. Попередні звіти не перезаписуються. Поточні `field_exact_accuracy` означають повну відповідність за версійованою політикою, включно з підтвердженим перекладом; це не буквальна рівність рядків і не доведена універсальна семантична accuracy.

Нормалізація поділена на чотири рівні: **subject identity → property concept → quantity/unit → context**. У `policy.py` перелічено закриті словники `ENTITY_CONCEPTS`, `PROPERTY_CONCEPTS`, `PROPERTY_FAMILIES`, `ROLE_CONCEPTS`, `STATEMENT_CONCEPTS`. Наприклад: Tilt Sensor Module/Модуль датчика наклона/Модуль датчика нахилу; Operating Voltage/Рабочее напряжение/Робоча напруга; Board Size/Размеры платы/Розміри плати. Це загальні технічні терміни, а не повні golden-відповіді або правила певного провайдера. Непокриті уточнення, заперечення та додаткові функції не викидаються.

Назва властивості в subject (`Operating Voltage`) не доводить предмет характеристики. Такі записи зіставляються другим проходом лише як `candidate_pairs`, після підтверджених пар. Це не дає TP. Якщо предмет невідомий, навіть розбіжність числа зберігається як умовна (`conditional_verdict`), а не доведена помилка того самого факту. Неоднозначні кандидати залишаються review-групами. Значення не використовується для вибору пристрою.

Для компонентів identity може підтверджувати явна повна модель у назві, з межами слова: ABC1 не означає ABC10. Це не виправляє model/manufacturer у JSON. R1/C1/K1, `used`, `N/A`, загальний `microchip` не доводять модель. Uno/Mega, плата/мікроконтролер та модуль/чутливий елемент не зливаються. Uno без ревізії не суперечить rev.3, але непідтверджені атрибути все одно не проходять full_fact.

Числовий розбір додатково підтримує одиницю всередині value при `unit=null`, градуси та впорядковані 2D/3D розміри. `3,2 × 1,4 см` еквівалентне `3.2 cm x 1.4 cm`; порядок осей зберігається, площа 4.48 не прирівнюється до розмірів. `45–130°` еквівалентне `45 to 130 degrees`; точка 45 не дорівнює діапазону. Невідповідність явної unit і вбудованої одиниці не ігнорується. Status markers UA/RU/EN зберігаються й перевіряються окремо від назви характеристики.

Відомий фізичний тип також перевіряється: `Board Size` у вольтах або `Current Consumption = real-time monitoring` не дає підтвердженого числового факту навіть при однакових рядках. Непрозорий запис такого типу лишається review; конфігураційний пін A4 можна порівнювати текстово. Це перевірка узгодженості форми факту, а не додавання невідомих характеристик обладнання.

`fact_assessment` у summary/details показує full matches, суперечності еталону за підтвердженої identity, review-пари, missing/extra та непідтверджені атрибути. Відсутня модель/виробник у golden не є доказом галюцинації прогнозу. Консервативні FP/FN зберігаються, але не підміняють цю діагностику.

### Відтворення до/після

Результати старої політики зафіксовано **до** редагування коду в `results/evaluation-semantic-v1-baseline`. Нова оцінка — `results/evaluation-semantic-v2`. В обох каталогах є `controls.json`, що містить ті самі 43 контрольні факти і фактичні рішення політики. Джерело контрольних випадків — `tests/fixtures/semantic_controls.json`; вони не є golden set.

```powershell
.\.venv\Scripts\python.exe evaluate.py --golden data/sourses/hm1/golden.json --runs results/step1 results/step2 --output-dir results/evaluation-next-policy
.\.venv\Scripts\python.exe -m tests.semantic_controls --output results/evaluation-next-policy/controls.json
.\.venv\Scripts\python.exe compare_evaluators.py --before results/evaluation-semantic-v1-baseline --after results/evaluation-next-policy --controls-before results/evaluation-semantic-v1-baseline/controls.json --controls-after results/evaluation-next-policy/controls.json --output-dir results/evaluation-next-policy
```

Порівняльний CLI перевіряє однакові fingerprints входів, конфігурації, ID та самі контрольні твердження. Він створює `before_after.json` і `before_after.md`, відхиляє їх перезапис. FN-fixed — тільки позитивні контрольні факти, які раніше не мали match, а тепер підтверджені. FP — негативні/review контролі, які помилково стали match; звіт показує і нові FP, якщо вони з’явилися. Нуль FP на 24 контролях не доводить їх відсутності в усіх статтях.

У реальному HR-0068 три потенційні числові збіги можуть лишатися review через subject, який називає властивість замість пристрою. Це очікувана межа доказовості, а не підстава додати документоспецифічний alias. Новий F1 може не зрости: відповідність повного факту потребує підтвердження всіх його частин. Усі висновки залишаються provisional до ручної перевірки еталонів.
