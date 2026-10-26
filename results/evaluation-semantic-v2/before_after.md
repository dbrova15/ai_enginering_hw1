# Semantic matching: до та після

Статус: **provisional**. golden-evaluator-v1.0 → golden-evaluator-v2.0.

Golden set, TXT, промпт і відповіді моделей ідентичні за SHA-256. Моделі повторно не запускалися. Зміни нижче спричинені лише evaluator. Зростання F1 саме по собі не доводить виправлення.

| Модель / метрика | Попередній оцінювач | Оновлений оцінювач |
| --- | --- | --- |
| gpt-4o-mini / Components Identity F1 | 38.30% | 41.13% |
| gpt-4o-mini / Components Full Fact F1 | 0.00% | 0.00% |
| gpt-4o-mini / Technical Parameters F1 | 0.00% | 0.00% |
| gpt-4o-mini / main_subject confirmed field accuracy | 0.00% | 0.00% |
| gpt-4o-mini / purpose confirmed field accuracy | 0.00% | 0.00% |
| gpt-4o-mini / needs_review (atomic checks) | 59 | 68 |
| llama3.2:3b / Components Identity F1 | 18.63% | 18.63% |
| llama3.2:3b / Components Full Fact F1 | 0.00% | 0.00% |
| llama3.2:3b / Technical Parameters F1 | 0.00% | 0.00% |
| llama3.2:3b / main_subject confirmed field accuracy | 0.00% | 0.00% |
| llama3.2:3b / purpose confirmed field accuracy | 0.00% | 0.00% |
| llama3.2:3b / needs_review (atomic checks) | 44 | 46 |
| False negatives на 19 спільних позитивних контролях | 16 | 0 |
| False positives на 24 спільних негативних/review контролях | 0 | 0 |

Контролі — синтетичні підтверджені факти, однакові для всіх моделей; це не частота помилок на корпусі. needs_review checks мають змінну кількість перевірок: їхнє число не є зіставною accuracy. Підтверджений переклад назви не скасовує неправильний model/manufacturer/role.

## Виправлені false negatives на контролях

Підтверджено виправлено: **16**. Нових false positives: **0**.

`angle_range`, `board_dimensions`, `dimensions_scale`, `jumper_translation`, `microampere_alias`, `operating_voltage_en`, `operating_voltage_ru`, `operating_voltage_uk`, `potentiometer_translation`, `purpose_measure_temperature`, `purpose_watering_translation`, `role_translation`, `subject_tilt_translation`, `subject_watering_translation`, `tilt_module_translation`, `voltage_inline_unit`

## Реальні зміни та невизначені випадки

### gpt-4o-mini / HR-0068 / components

new_identity_match; expected[11] ↔ predicted[3]; повний збіг: False; verdict: needs_review.

Перевірки: name=match; model=match; manufacturer=match; role=needs_review.

### gpt-4o-mini / HR-0068 / components

new_identity_match; expected[0] ↔ predicted[1]; повний збіг: False; verdict: mismatch.

Перевірки: name=match; model=mismatch; manufacturer=match; role=needs_review.

### gpt-4o-mini / HR-0068 / technical_parameters

new_review_candidate; expected[4] ↔ predicted[3]; повний збіг: False; verdict: needs_review.

Перевірки: subject=needs_review; name=match; value=match; unit=match; context=match.

### gpt-4o-mini / HR-0068 / technical_parameters

new_review_candidate; expected[0] ↔ predicted[1]; повний збіг: False; verdict: needs_review.

Перевірки: subject=needs_review; name=match; value=match; unit=match; context=match.

### gpt-4o-mini / HR-0068 / components

removed_identity_match; expected[1] ↔ predicted[1]; повний збіг: False; verdict: None.

Перевірки: name=needs_review; model=match; manufacturer=match; role=needs_review.

Це колишня пара, яку новий evaluator не підтверджує. Наведені checks належать попередній політиці. Спільний код не доводить, що модуль і окремий чутливий елемент — одна апаратна сутність; зниження identity F1 також потребує аналізу.

- gpt-4o-mini / components: review-пар 10, неоднозначних груп 0, суперечностей еталону за підтвердженої identity 2.
- gpt-4o-mini / technical_parameters: review-пар 6, неоднозначних груп 1, суперечностей еталону за підтвердженої identity 0.
### llama3.2:3b / HR-0068 / technical_parameters

new_review_candidate; expected[0] ↔ predicted[1]; повний збіг: False; verdict: needs_review.

Перевірки: subject=needs_review; name=needs_review; value=match; unit=match; context=match.

- llama3.2:3b / components: review-пар 1, неоднозначних груп 0, суперечностей еталону за підтвердженої identity 7.
- llama3.2:3b / technical_parameters: review-пар 1, неоднозначних груп 1, суперечностей еталону за підтвердженої identity 0.

## Висновок та обмеження достовірності

Контрольні переклади, одиниці, діапазони й розміри розпізнаються без злиття негативних контролів. Це доказ на контрольному наборі, а не гарантія відсутності false positives на всіх документах. Непідтверджені subjects, невідомі терміни, часткові purpose та конфлікт HR-0207 лишаються review. Консервативні FP/FN включають такі факти, але не називають їх доведеними помилками моделі. Новий словник не виправляє вхідні атрибути та не доповнює їх зовнішніми знаннями.

За наявними даними неможливо впевнено визначити кращу модель: еталони provisional, лише 10 документів, словник обмежений. Потрібна ручна перевірка кандидатів і дослідження помилок обох моделей за однією політикою. Контрольні позначки й обидва snapshots збережені.
