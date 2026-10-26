# Промпти Schema v2

## v1 — 26.10.2026

Нейтральний baseline восьми простих полів; JSON Schema передається окремо.
Без Component/TechnicalParameter, golden-прикладів і виправлень, нібито
підтверджених ще не виконаним експериментом. Старий prompts/v1.txt незмінний.

## v2 — 26.10.2026, frozen після baseline60

SHA-256: `ba3e83f178b927849caa401cd7b22ebe06381c4eb4fb0977b2c7e5ca2a36394d`. Підстава — results/schema_v2/development_notes.md; D∩G=∅, три вручну прочитані non-golden TXT. G прогнози не використані для tuning.

| Факт baseline D | Зміна | Гіпотеза |
| --- | --- | --- |
| HR-0056 GPT пропустив USB; OSS додав UART | Всі прямі згадки, включно із запереченнями; не виводити UART з MCU/ADC/SWD/Serial | Менше FN інтерфейсів і FP UART |
| HR-0221 GPT пропустив UART | Повторно перевірити увесь текст | Менше пропусків другорядного інтерфейсу |
| HR-0056 GPT та HR-0221 OSS battery=true без батареї | Відділити battery від джерела живлення/USB/DC-DC | Менше FP battery |
| HR-0221 OSS display=true через звичайний LED | Явна межа display/LED | Менше FP display |
| HR-0221 OSS topic=printing_mechanics для термореле; HR-0056 OSS topic за кодом | Домінантна мета й визначення восьми тем | Менше хибної тематики без підміни enum |

### Виміряний результат на approved G=10

Після120 primary: GPT content=62/70 для v1 і v2 при обох sampling — aggregate покращення немає. На T0 interfaces recall3/7→4/7, F1 .600→.667, але FP0→1. На T07 recall3/7→5/7, FP0→2, topic accuracy10/10→9/10; content знову62/70. Llama content T0:29→30/70; T07:35→24/70. Гіпотеза не дала стабільного загального покращення; v2 не оголошено переможцем.

Джерело: results/schema_v2/evaluation-final/summary.json, REPORT.md. Текст v2 після freeze не змінювався; few-shot чи ID у промпті немає. Автор погодив conservative production config schema_v2/v1/T0 26.10.2026.
