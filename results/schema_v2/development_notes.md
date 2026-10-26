# Development notes — Schema v2

Дата: 26.10.2026. D визначено до запусків: HR-0001, HR-0055, HR-0056, HR-0221. G: HR-0068, HR-0187, HR-0207, HR-0212, HR-0227, HR-0244, HR-0254, HR-0385, HR-0415, HR-0743. D∩G=∅ перевірено.

Вручну прочитано 3 повні non-golden TXT: HR-0056, HR-0055, HR-0221. HR-0001 — резервний четвертий D, не використано для tuning. Не створювався новий великий golden. До freeze prompt-v2 прогнози на G не відкривалися й accuracy на G не рахувалася.

| D / рядки | Факт TXT | Спостереження baseline | Зміна/гіпотеза |
| --- | --- | --- | --- |
| HR-0056:33 | Явна згадка USB, навіть у рекомендації не живити від комп’ютера | GPT interfaces=[]; OSS interfaces=[uart] | Збирати всі прямі згадки enum у змісті, включно із запереченнями/альтернативами; не домислювати UART з MCU/ADC |
| HR-0056:25,33,111–145 | LCD, USB і джерело живлення; батареї немає | GPT mentions_battery=true | Блок живлення/5V/3.3V не доводять батарею |
| HR-0221:25 | UART прямо названий | GPT interfaces=[wifi] без uart | Перечитати всю статтю: додатковий інтерфейс може бути поза головним описом Wi-Fi |
| HR-0055:10,28,38–60,124 | Явний SPI у prose і коді; stm32; sensor і LCD | Обидва правильно визначили stm32/spi/sensor/display/battery=false; topics відрізняються | Контрольний текст: не вводити вузький few-shot і не міняти enum. Спірна topic-інтерпретація сама не доводить помилку |

Baseline artifacts (тільки D):

- GPT-v1-T0/run_a94e1b186c7b4a8daed61364665143ad.json: HR-0221, status=success, result={"language": "uk", "primary_topic": "devices_automation", "mentioned_platforms": ["esp8266"], "mentioned_interfaces": ["wifi"], "mentions_sensor": true, "mentions_display": false, "mentions_battery": false, "mentions_motor": true}
- GPT-v1-T0/run_b883450564c742d1930af55c164913ed.json: HR-0055, status=success, result={"language": "uk", "primary_topic": "sensors_measurements", "mentioned_platforms": ["stm32"], "mentioned_interfaces": ["spi"], "mentions_sensor": true, "mentions_display": true, "mentions_battery": false, "mentions_motor": false}
- GPT-v1-T0/run_e1365e7c56ea46a18b05afa716fe28d1.json: HR-0056, status=success, result={"language": "uk", "primary_topic": "sensors_measurements", "mentioned_platforms": ["stm32"], "mentioned_interfaces": [], "mentions_sensor": true, "mentions_display": true, "mentions_battery": true, "mentions_motor": false}
- OSS-v1-T0/run_030be19327094f8c9c747498d010d6c5.json: HR-0221, status=success, result={"language": "uk", "primary_topic": "printing_mechanics", "mentioned_platforms": ["esp8266"], "mentioned_interfaces": ["wifi", "uart"], "mentions_sensor": true, "mentions_display": true, "mentions_battery": true, "mentions_motor": true}
- OSS-v1-T0/run_c6268794602b40be84016fa35ecb784f.json: HR-0055, status=success, result={"language": "uk", "primary_topic": "controllers_programming", "mentioned_platforms": ["stm32"], "mentioned_interfaces": ["spi"], "mentions_sensor": true, "mentions_display": true, "mentions_battery": false, "mentions_motor": false}
- OSS-v1-T0/run_fd42d387c7944195b402378300b0bfc6.json: HR-0056, status=success, result={"language": "uk", "primary_topic": "controllers_programming", "mentioned_platforms": ["stm32"], "mentioned_interfaces": ["uart"], "mentions_sensor": true, "mentions_display": true, "mentions_battery": false, "mentions_motor": false}

Немає виправлень за expected або помилками фінального G. Попередня розробка v1/semantic evaluator вже використовувала G; це розкритий ризик незалежності, не сліпий holdout.

Prompt-v2 створюється тільки після завершення baseline60. Гіпотеза: нагадування прямої згадки/повного тексту зменшить FP battery/UART і FN USB/UART; реальний ефект на G поки невідомий. Після freeze prompt не змінювати за G feedback.

Додаткові перевірені помилки D: OSS HR-0221 mentions_display=true при лише звичайному LED у :25; mentions_battery=true за відсутності батареї в повному змісті; primary_topic=printing_mechanics, хоча :5–7 описують термореле й дистанційне керування. Гіпотеза: явні межі display/battery і визначення topic за метою зменшать такі FP/хибний клас. Тема HR-0055 лишається спірною і не слугує ціллю виправлення.
