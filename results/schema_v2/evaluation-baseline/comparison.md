# Порівняння Schema v2

Еталон: **approved**. Політика: schema-v2-evaluator-v1.0.
Якість і runtime нижче — тільки golden set; missing/invalid залишаються у знаменниках.

| Експеримент | Primary N | Content | Aggregate | Valid/G | p50 / p95, с |
| --- | --- | --- | --- | --- | --- |
| GPT-v1-T0 | 30/30 | 88.6% (62/70) | 90.0% (72/80) | 100.0% (10/10) | 1.3237148499465548 / 1.5058248099463525 |
| OSS-v1-T0 | 30/30 | 41.4% (29/70) | 45.0% (36/80) | 70.0% (7/10) | 3.2387840000446886 / 28.403574715001742 |

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

## OSS-v1-T0

| Поле | Accuracy |
| --- | --- |
| language | 70.0% (7/10) |
| primary_topic | 30.0% (3/10) |
| mentioned_platforms | 30.0% (3/10) |
| mentioned_interfaces | 40.0% (4/10) |
| mentions_sensor | 40.0% (4/10) |
| mentions_display | 60.0% (6/10) |
| mentions_battery | 40.0% (4/10) |
| mentions_motor | 50.0% (5/10) |

mentioned_platforms: TP=5, FP=2, FN=5; P=0.7142857142857143, R=0.5, F1=0.5882352941176471.

mentioned_interfaces: TP=5, FP=5, FN=2; P=0.5, R=0.7142857142857143, F1=0.5882352941176471.

Latency known n=10; cold start=unknown_not_separated. Токени, вартість та їх coverage див. summary.json → runtime.usage.

