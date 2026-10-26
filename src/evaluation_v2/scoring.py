"""Точне оцінювання enum/bool/list[enum]; жодних aliases або semantic credits."""

from src.evaluation.runtime import ratio

FIELDS = ('language', 'primary_topic', 'mentioned_platforms', 'mentioned_interfaces',
          'mentions_sensor', 'mentions_display', 'mentions_battery', 'mentions_motor')
LISTS = ('mentioned_platforms', 'mentioned_interfaces')


def score(expected: dict, predicted: dict | None) -> dict:
    """Порівнює всі поля; missing prediction не дорівнює false або порожньому списку."""
    fields = {}
    for field in FIELDS:
        gold = expected[field]
        actual = predicted[field] if predicted is not None else None
        item = {'expected': gold, 'predicted': actual, 'correct': predicted is not None and gold == actual}
        if field in LISTS:
            left, right = set(gold), set(actual or [])
            item.update(correct=predicted is not None and left == right,
                        tp=len(left & right), fp=len(right - left), fn=len(left - right),
                        missing=sorted(left - right), extra_predicted=sorted(right - left))
        fields[field] = item
    return fields


def aggregate(documents: list) -> dict:
    """Рахує fixed-G accuracy і незалежні micro метрики двох списків."""
    size = len(documents)
    accuracies = {field: ratio(sum(d['fields'][field]['correct'] for d in documents), size,
                              'correct/G; missing and invalid=incorrect', 'golden_10' if size == 10 else 'all golden IDs')
                  for field in FIELDS}
    lists = {}
    for field in LISTS:
        tp, fp, fn = (sum(d['fields'][field][k] for d in documents) for k in ('tp', 'fp', 'fn'))
        lists[field] = {'tp': tp, 'fp': fp, 'fn': fn,
                        'precision': ratio(tp, tp + fp, 'TP/(TP+FP)', 'golden tags'),
                        'recall': ratio(tp, tp + fn, 'TP/(TP+FN)', 'golden tags'),
                        'f1': ratio(2 * tp, 2 * tp + fp + fn, '2TP/(2TP+FP+FN)', 'golden tags')}
    return {'field_accuracy': accuracies, 'language_accuracy': accuracies['language'],
            'aggregate_accuracy': ratio(sum(v['numerator'] for v in accuracies.values()), 8 * size,
                                        'correct fields/(8G)', 'all golden IDs'),
            'content_accuracy': ratio(sum(accuracies[f]['numerator'] for f in FIELDS if f != 'language'),
                                      7 * size, 'correct content fields/(7G)', 'golden without language'),
            'lists': lists}
