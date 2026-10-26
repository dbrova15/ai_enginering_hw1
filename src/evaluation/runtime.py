"""Спільні runtime-метрики без імпорту schema-specific або semantic scorer.

Формули й сигнатури v1 збережені; v2 використовує ті самі правила
unknown/usage/retry/repair, передаючи власні валідовані RunRecord.
"""

import math
from collections import Counter

from src.evaluation.usage import number, usage_metrics


def ratio(numerator: int, denominator: int, method: str, basis: str) -> dict:
    """Повертає частку з її підставою; нульовий знаменник означає undefined."""
    return {'value': numerator / denominator if denominator else None,
            'numerator': numerator, 'denominator': denominator, 'method': method, 'basis': basis,
            'undefined_reason': None if denominator else 'undefined_no_items'}


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

