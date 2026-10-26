# Порівняння Schema v2

Еталон: **approved**. Політика: schema-v2-evaluator-v1.0.
Якість і runtime нижче — тільки golden set; missing/invalid залишаються у знаменниках.

| Експеримент | Primary N | Content | Aggregate | Valid/G | p50 / p95, с |
| --- | --- | --- | --- | --- | --- |
| OSS-v2-T0 | 10/10 | 42.9% (30/70) | 46.2% (37/80) | 70.0% (7/10) | 3.7832800000323914 / 29.776901659992287 |

## OSS-v2-T0

| Поле | Accuracy |
| --- | --- |
| language | 70.0% (7/10) |
| primary_topic | 40.0% (4/10) |
| mentioned_platforms | 40.0% (4/10) |
| mentioned_interfaces | 0.0% (0/10) |
| mentions_sensor | 60.0% (6/10) |
| mentions_display | 50.0% (5/10) |
| mentions_battery | 60.0% (6/10) |
| mentions_motor | 50.0% (5/10) |

mentioned_platforms: TP=6, FP=1, FN=4; P=0.8571428571428571, R=0.6, F1=0.7058823529411765.

mentioned_interfaces: TP=3, FP=21, FN=4; P=0.125, R=0.42857142857142855, F1=0.1935483870967742.

Latency known n=10; cold start=unknown_not_separated. Токени, вартість та їх coverage див. summary.json → runtime.usage.

