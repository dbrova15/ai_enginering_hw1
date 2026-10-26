# Порівняння Schema v2

Еталон: **approved**. Політика: schema-v2-evaluator-v1.0.
Якість і runtime нижче — тільки golden set; missing/invalid залишаються у знаменниках.

| Експеримент | Primary N | Content | Aggregate | Valid/G | p50 / p95, с |
| --- | --- | --- | --- | --- | --- |
| OSS-v1-T0 | 30/30 | 41.4% (29/70) | 45.0% (36/80) | 70.0% (7/10) | 3.2387840000446886 / 28.403574715001742 |

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

