"""Прозорі агрегати: явні знаменники, повне покриття golden і невідомі виміри."""

from collections import Counter

from src.evaluation.scoring import FIELDS, LISTS
from src.evaluation.runtime import ratio, percentile, runtime_metrics




def prf(counts: dict, basis: str) -> dict:
    """Рахує micro PR/F1 з TP/FP/FN; порожні множини не отримують вигаданих 100%."""
    tp, fp, fn = (counts[k] for k in ('tp', 'fp', 'fn'))
    return {**counts, 'precision': ratio(tp, tp + fp, 'TP/(TP+FP)', basis),
            'recall': ratio(tp, tp + fn, 'TP/(TP+FN)', basis),
            'f1': ratio(2 * tp, 2 * tp + fp + fn, '2TP/(2TP+FP+FN)', basis)}






def aggregate_quality(documents: list) -> dict:
    """Зберігає знаменник усіх golden документів і незалежні exact та PR/F1 метрики."""
    size = len(documents)
    exact = {field: ratio(sum(d['fields'][field]['exact'] for d in documents), size,
                           'whole field exact/G; missing/invalid are not correct', 'all golden IDs')
             for field in FIELDS}
    lists = {}
    for field in LISTS:
        lists[field] = {}
        for mode in (('identity', 'full_fact') if field == 'components' else ('full_fact',)):
            totals = {k: sum(d['fields'][field][mode][k] for d in documents)
                      for k in ('tp', 'fp', 'fn', 'expected', 'predicted')}
            lists[field][mode] = prf(totals, 'all golden objects including unavailable predictions')
    checks = [c for d in documents for f in d['fields'].values() for c in f['checks']]
    verdicts = Counter(c['verdict'] for c in checks)
    review_documents = sum(any(c['verdict'] == 'needs_review' for f in d['fields'].values()
                               for c in f['checks']) for d in documents)
    attributes = {}
    for name in ('model', 'manufacturer', 'role'):
        attribute_checks = [c for c in checks if c['check_id'].startswith('components[')
                            and c['check_id'].endswith('.' + name)]
        attributes[name] = {'correct_over_paired': ratio(sum(c['verdict'] == 'match' for c in attribute_checks),
                              len(attribute_checks), 'correct attribute/paired identity checks', 'paired components only'),
                            'verdict_counts': dict(Counter(c['verdict'] for c in attribute_checks))}
    return {'golden_documents': size, 'field_exact_accuracy': exact,
            'aggregate_exact_accuracy': ratio(sum(m['numerator'] for m in exact.values()), 8 * size,
                                              'sum field exact/(8*G)', 'all golden IDs and eight fields'),
            'lists': lists, 'component_attributes': attributes,
            'fact_assessment': fact_assessment(documents),
            'review': {'check_counts': dict(verdicts), 'total_checks': len(checks),
                       'auto_decided_checks': verdicts['match'] + verdicts['mismatch'],
                       'unavailable_checks': verdicts['unavailable_prediction'],
                       'needs_review': ratio(verdicts['needs_review'], len(checks), 'review/total atomic checks', 'atomic checks'),
                       'documents': ratio(review_documents, size, 'review documents/G', 'all golden IDs'),
                       'ambiguous_pairing_groups': sum(len(f.get('ambiguous_pairing_groups', []))
                                                      for d in documents for f in d['fields'].values())}}


def fact_assessment(documents: list) -> dict:
    """Рахує рішення щодо пар окремо від атомарних checks і консервативних FP/FN.

    Contradictions — суперечності з еталоном при підтвердженій identity,
    не зовнішній доказ галюцинації. Невідомий subject не рахується помилкою.
    """
    result = {}
    for field in ('components', 'technical_parameters'):
        facts = [d['fields'][field] for d in documents]
        keys = ('confirmed_matches', 'confirmed_contradictions', 'needs_review_pairs',
                'unsupported_attribute_pairs', 'missing', 'extra_predicted')
        result[field] = {key: sum(f.get('fact_assessment', {}).get(key, 0) for f in facts) for key in keys}
        result[field]['missing'] += sum(len(f.get('missing', [])) for f in facts if 'fact_assessment' not in f)
        result[field]['ambiguous_groups'] = sum(len(f.get('ambiguous_pairing_groups', [])) for f in facts)
        result[field]['method'] = 'pair decisions; not disjoint categories; conservative PR/F1 retained'
    return result
