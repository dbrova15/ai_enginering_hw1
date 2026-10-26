# Порівняння Schema v2

Еталон: **approved**. Політика: schema-v2-evaluator-v1.0.
Якість і runtime нижче — тільки golden set; missing/invalid залишаються у знаменниках.

| Експеримент | Primary N | Content | Aggregate | Valid/G | p50 / p95, с |
| --- | --- | --- | --- | --- | --- |
| OSS-v2-T07 | 10/10 | 34.3% (24/70) | 35.0% (28/80) | 50.0% (5/10) | 3.3546662999433465 / 17.419217520003414 |

## OSS-v2-T07

| Поле | Accuracy |
| --- | --- |
| language | 40.0% (4/10) |
| primary_topic | 20.0% (2/10) |
| mentioned_platforms | 30.0% (3/10) |
| mentioned_interfaces | 10.0% (1/10) |
| mentions_sensor | 50.0% (5/10) |
| mentions_display | 40.0% (4/10) |
| mentions_battery | 50.0% (5/10) |
| mentions_motor | 40.0% (4/10) |

mentioned_platforms: TP=3, FP=0, FN=7; P=1.0, R=0.3, F1=0.46153846153846156.

mentioned_interfaces: TP=1, FP=11, FN=6; P=0.08333333333333333, R=0.14285714285714285, F1=0.10526315789473684.

Latency known n=10; cold start=unknown_not_separated. Токени, вартість та їх coverage див. summary.json → runtime.usage.

