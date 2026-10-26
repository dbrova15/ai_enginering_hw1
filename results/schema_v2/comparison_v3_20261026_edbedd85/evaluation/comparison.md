# Порівняння Schema v2

Еталон: **approved**. Політика: schema-v2-evaluator-v1.0.
Якість і runtime нижче — тільки golden set; missing/invalid залишаються у знаменниках.

| Експеримент | Primary N | Content | Aggregate | Valid/G | p50 / p95, с |
| --- | --- | --- | --- | --- | --- |
| GPT-v3-T0 | 30/30 | 88.6% (62/70) | 90.0% (72/80) | 100.0% (10/10) | 1.5646762499818578 / 2.168179560021963 |
| OSS-v3-T0 | 30/30 | 40.0% (28/70) | 38.8% (31/80) | 70.0% (7/10) | 3.2623074999428354 / 18.774828159983706 |

## GPT-v3-T0

| Поле | Accuracy |
| --- | --- |
| language | 100.0% (10/10) |
| primary_topic | 100.0% (10/10) |
| mentioned_platforms | 90.0% (9/10) |
| mentioned_interfaces | 60.0% (6/10) |
| mentions_sensor | 90.0% (9/10) |
| mentions_display | 90.0% (9/10) |
| mentions_battery | 100.0% (10/10) |
| mentions_motor | 90.0% (9/10) |

mentioned_platforms: TP=9, FP=0, FN=1; P=1.0, R=0.9, F1=0.9473684210526315.

mentioned_interfaces: TP=3, FP=1, FN=4; P=0.75, R=0.42857142857142855, F1=0.5454545454545454.

Latency known n=10; cold start=unknown_not_separated. Токени, вартість та їх coverage див. summary.json → runtime.usage.

## OSS-v3-T0

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

