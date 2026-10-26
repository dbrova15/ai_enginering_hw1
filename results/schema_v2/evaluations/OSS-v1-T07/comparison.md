# Порівняння Schema v2

Еталон: **approved**. Політика: schema-v2-evaluator-v1.0.
Якість і runtime нижче — тільки golden set; missing/invalid залишаються у знаменниках.

| Експеримент | Primary N | Content | Aggregate | Valid/G | p50 / p95, с |
| --- | --- | --- | --- | --- | --- |
| OSS-v1-T07 | 10/10 | 50.0% (35/70) | 52.5% (42/80) | 80.0% (8/10) | 3.0980914999963716 / 3.7850511699740306 |

## OSS-v1-T07

| Поле | Accuracy |
| --- | --- |
| language | 70.0% (7/10) |
| primary_topic | 30.0% (3/10) |
| mentioned_platforms | 60.0% (6/10) |
| mentioned_interfaces | 40.0% (4/10) |
| mentions_sensor | 40.0% (4/10) |
| mentions_display | 70.0% (7/10) |
| mentions_battery | 60.0% (6/10) |
| mentions_motor | 50.0% (5/10) |

mentioned_platforms: TP=7, FP=1, FN=3; P=0.875, R=0.7, F1=0.7777777777777778.

mentioned_interfaces: TP=3, FP=5, FN=4; P=0.375, R=0.42857142857142855, F1=0.4.

Latency known n=10; cold start=unknown_not_separated. Токени, вартість та їх coverage див. summary.json → runtime.usage.

