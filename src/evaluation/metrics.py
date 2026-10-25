"""Прозорі агрегати: явні знаменники, повне покриття golden і невідомі виміри."""

import math
from collections import Counter

from src.evaluation.scoring import FIELDS, LISTS
from src.evaluation.usage import number, usage_metrics


def ratio(numerator: int, denominator: int, method: str, basis: str) -> dict:
    """Повертає частку з її підставою; нульовий знаменник означає undefined."""
    return {'value': numerator / denominator if denominator else None,
            'numerator': numerator, 'denominator': denominator, 'method': method, 'basis': basis,
            'undefined_reason': None if denominator else 'undefined_no_items'}


def prf(counts: dict, basis: str) -> dict:
    """Рахує micro PR/F1 з TP/FP/FN; порожні множини не отримують вигаданих 100%."""
    tp, fp, fn = (counts[k] for k in ('tp', 'fp', 'fn'))
    return {**counts, 'precision': ratio(tp, tp + fp, 'TP/(TP+FP)', basis),
            'recall': ratio(tp, tp + fn, 'TP/(TP+FN)', basis),
            'f1': ratio(2 * tp, 2 * tp + fp + fn, '2TP/(2TP+FP+FN)', basis)}


def percentile(values: list, q: float) -> float | None:
    """Інтерполює квантиль за позицією (n−1)q; не змінює переданий список."""
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def runtime_metrics(runs: list, pricing: list) -> dict:
    """Рахує структурну валідність і runtime на всіх runs, а не лише успішних."""
    total = len(runs)
    first_known = [r.first_valid for r in runs if r.first_valid is not None]
    latency = [r.data['latency_seconds'] for r in runs if number(r.data.get('latency_seconds'))]
    return {
        'documents': total, 'status_counts': dict(Counter(r.data.get('status', 'unknown') for r in runs)),
        'valid_final': ratio(sum(r.result is not None for r in runs), total, 'validated result/A', 'all runs'),
        'valid_first_known': ratio(sum(first_known), len(first_known), 'true/known first attempts', 'known first attempts'),
        'first_attempt_coverage': ratio(len(first_known), total, 'known/A', 'all runs'),
        'valid_first_confirmed': ratio(sum(first_known), total, 'confirmed true/A', 'all runs'),
        'unknown_first_attempts': total - len(first_known),
        'latency': {'p50': percentile(latency, .5), 'p95': percentile(latency, .95),
                    'mean': sum(latency) / len(latency) if latency else None,
                    'known_sum': sum(latency) if latency else None,
                    'sample_count': len(latency), 'unknown_count': total - len(latency),
                    'numerator': None, 'denominator': None, 'basis': 'all runs with known latency_seconds',
                    'method': 'pipeline latency; linear interpolation (n-1)*q; includes recorded retry/repair',
                    'primary_attempt_latency': None, 'cold_start': 'unknown_not_separated'},
        'usage': usage_metrics(runs, pricing),
        'problems': [{'document_id': r.document_id, 'reasons': r.problems} for r in runs if r.problems],
    }


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
            'review': {'check_counts': dict(verdicts), 'total_checks': len(checks),
                       'auto_decided_checks': verdicts['match'] + verdicts['mismatch'],
                       'unavailable_checks': verdicts['unavailable_prediction'],
                       'needs_review': ratio(verdicts['needs_review'], len(checks), 'review/total atomic checks', 'atomic checks'),
                       'documents': ratio(review_documents, size, 'review documents/G', 'all golden IDs'),
                       'ambiguous_pairing_groups': sum(len(f.get('ambiguous_pairing_groups', []))
                                                      for d in documents for f in d['fields'].values())}}
