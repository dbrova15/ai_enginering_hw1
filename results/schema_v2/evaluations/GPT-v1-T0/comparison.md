# Порівняння Schema v2

Еталон: **approved**. Політика: schema-v2-evaluator-v1.0.
Якість і runtime нижче — тільки golden set; missing/invalid залишаються у знаменниках.

| Експеримент | Primary N | Content | Aggregate | Valid/G | p50 / p95, с |
| --- | --- | --- | --- | --- | --- |
| GPT-v1-T0 | 30/30 | 88.6% (62/70) | 90.0% (72/80) | 100.0% (10/10) | 1.3237148499465548 / 1.5058248099463525 |

## GPT-v1-T0

| Поле | Accuracy |
| --- | --- |
| language | 100.0% (10/10) |
| primary_topic | 100.0% (10/10) |
| mentioned_platforms | 90.0% (9/10) |
| mentioned_interfaces | 70.0% (7/10) |
| mentions_sensor | 80.0% (8/10) |
| mentions_display | 90.0% (9/10) |
| mentions_battery | 100.0% (10/10) |
| mentions_motor | 90.0% (9/10) |

mentioned_platforms: TP=9, FP=0, FN=1; P=1.0, R=0.9, F1=0.9473684210526315.

mentioned_interfaces: TP=3, FP=0, FN=4; P=1.0, R=0.42857142857142855, F1=0.6.

Latency known n=10; cold start=unknown_not_separated. Токени, вартість та їх coverage див. summary.json → runtime.usage.

