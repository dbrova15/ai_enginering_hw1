# Порівняння Schema v2

Еталон: **approved**. Політика: schema-v2-evaluator-v1.0.
Якість і runtime нижче — тільки golden set; missing/invalid залишаються у знаменниках.

| Експеримент | Primary N | Content | Aggregate | Valid/G | p50 / p95, с |
| --- | --- | --- | --- | --- | --- |
| GPT-v1-T0 | 30/30 | 88.6% (62/70) | 90.0% (72/80) | 100.0% (10/10) | 1.3237148499465548 / 1.5058248099463525 |
| GPT-v2-T0 | 10/10 | 88.6% (62/70) | 90.0% (72/80) | 100.0% (10/10) | 1.4048525000107475 / 1.5098651400592644 |
| OSS-v2-T07 | 10/10 | 34.3% (24/70) | 35.0% (28/80) | 50.0% (5/10) | 3.3546662999433465 / 17.419217520003414 |
| OSS-v1-T0 | 30/30 | 41.4% (29/70) | 45.0% (36/80) | 70.0% (7/10) | 3.2387840000446886 / 28.403574715001742 |
| GPT-v1-T07 | 10/10 | 88.6% (62/70) | 90.0% (72/80) | 100.0% (10/10) | 1.3253370999591425 / 1.6702082000148943 |
| GPT-v2-T07 | 10/10 | 88.6% (62/70) | 90.0% (72/80) | 100.0% (10/10) | 1.4520936000044458 / 1.5051297349738888 |
| OSS-v2-T0 | 10/10 | 42.9% (30/70) | 46.2% (37/80) | 70.0% (7/10) | 3.7832800000323914 / 29.776901659992287 |
| OSS-v1-T07 | 10/10 | 50.0% (35/70) | 52.5% (42/80) | 80.0% (8/10) | 3.0980914999963716 / 3.7850511699740306 |

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

## GPT-v2-T0

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

mentioned_interfaces: TP=4, FP=1, FN=3; P=0.8, R=0.5714285714285714, F1=0.6666666666666666.

Latency known n=10; cold start=unknown_not_separated. Токени, вартість та їх coverage див. summary.json → runtime.usage.

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

## GPT-v1-T07

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

## GPT-v2-T07

| Поле | Accuracy |
| --- | --- |
| language | 100.0% (10/10) |
| primary_topic | 90.0% (9/10) |
| mentioned_platforms | 90.0% (9/10) |
| mentioned_interfaces | 80.0% (8/10) |
| mentions_sensor | 80.0% (8/10) |
| mentions_display | 90.0% (9/10) |
| mentions_battery | 100.0% (10/10) |
| mentions_motor | 90.0% (9/10) |

mentioned_platforms: TP=9, FP=0, FN=1; P=1.0, R=0.9, F1=0.9473684210526315.

mentioned_interfaces: TP=5, FP=2, FN=2; P=0.7142857142857143, R=0.7142857142857143, F1=0.7142857142857143.

Latency known n=10; cold start=unknown_not_separated. Токени, вартість та їх coverage див. summary.json → runtime.usage.

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

