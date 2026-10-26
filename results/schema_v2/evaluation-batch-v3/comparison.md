# Порівняння Schema v2

Еталон: **approved**. Політика: schema-v2-evaluator-v1.0.
Якість і runtime нижче — тільки golden set; missing/invalid залишаються у знаменниках.

| Експеримент | Primary N | Content | Aggregate | Valid/G | p50 / p95, с |
| --- | --- | --- | --- | --- | --- |
| batch_v3 | 30/30 | 40.0% (28/70) | 38.8% (31/80) | 70.0% (7/10) | 3.2470919999759644 / 18.108635680022388 |

## batch_v3

| Поле | Accuracy |
| --- | --- |
| language | 30.0% (3/10) |
| primary_topic | 20.0% (2/10) |
| mentioned_platforms | 40.0% (4/10) |
| mentioned_interfaces | 10.0% (1/10) |
| mentions_sensor | 60.0% (6/10) |
| mentions_display | 50.0% (5/10) |
| mentions_battery | 50.0% (5/10) |
| mentions_motor | 50.0% (5/10) |

mentioned_platforms: TP=6, FP=3, FN=4; P=0.6666666666666666, R=0.6, F1=0.631578947368421.

mentioned_interfaces: TP=3, FP=11, FN=4; P=0.21428571428571427, R=0.42857142857142855, F1=0.2857142857142857.

Latency known n=10; cold start=unknown_not_separated. Токени, вартість та їх coverage див. summary.json → runtime.usage.

