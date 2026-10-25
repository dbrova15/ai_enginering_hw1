"""Облік токенів і вартості фактичних HTTP-запитів, без дублювання журналів."""

import math
from datetime import date
from decimal import Decimal
from pathlib import Path

from src.evaluation.loading import read_json
from src.evaluation.models import EvaluationError


def number(value) -> bool:
    """Перевіряє скінченне невід’ємне число; bool і відсутність не є виміром."""
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def load_pricing(path: Path | None) -> list[dict]:
    """Читає лише явно передані тарифи з датою/джерелом та точним маршрутом."""
    if path is None:
        return []
    rows = read_json(path)
    if not isinstance(rows, list):
        raise EvaluationError('Pricing повинен бути масивом тарифів.')
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise EvaluationError('Некоректний запис pricing.')
        key = tuple(row.get(k) for k in ('provider', 'requested_model', 'returned_model'))
        required = ('provider', 'requested_model', 'as_of', 'source_url')
        if any(not isinstance(row.get(k), str) or not row[k] for k in required):
            raise EvaluationError('Pricing потребує provider/model/as_of/source_url.')
        if row.get('currency') != 'USD' or not row['source_url'].startswith(('https://', 'http://')):
            raise EvaluationError('Pricing: потрібні USD і URL джерела.')
        try:
            date.fromisoformat(row['as_of'])
        except ValueError as exc:
            raise EvaluationError('Pricing: дата повинна мати формат YYYY-MM-DD.') from exc
        for rate in ('input_per_million', 'output_per_million', 'cached_input_per_million'):
            if rate == 'cached_input_per_million' and row.get(rate) is None:
                continue
            if not number(row.get(rate)):
                raise EvaluationError(f'Pricing: невалідний тариф {rate}.')
        if key in seen:
            raise EvaluationError('Pricing: дублікати тарифу для однієї конфігурації.')
        seen.add(key)
    return rows


def request_usages(data: dict) -> list[dict | None]:
    """Збирає usage кожного HTTP-запиту, використовуючи fallback лише без двозначності.

    Невдала спроба без usage зберігається як None: вона не перетворюється на
    нуль токенів або безкоштовний запит. Повторні копії attempt.usage не додаються.
    """
    collected = []
    for attempt in data.get('attempts', []):
        requests = attempt.get('requests')
        if isinstance(requests, list) and requests:
            for req in requests:
                response = req.get('response') if isinstance(req, dict) else None
                usage = response.get('usage') if isinstance(response, dict) else None
                if not isinstance(usage, dict) and len(requests) == 1:
                    usage = attempt.get('usage')
                collected.append(usage if isinstance(usage, dict) else None)
        else:
            collected.append(None)
    return collected or [None]


def _request_cost(usage: dict | None, config: dict, pricing: list) -> tuple:
    """Повертає ціну запиту з API або явного тарифу; невідоме залишається None."""
    if usage is None:
        return None, 'unknown'
    if number(usage.get('cost')):
        return Decimal(str(usage['cost'])), 'api_reported'
    row = next((p for p in pricing if all(p.get(k) == config.get(k)
                for k in ('provider', 'requested_model', 'returned_model'))), None)
    if row is None or not all(number(usage.get(k)) for k in ('prompt_tokens', 'completion_tokens')):
        return None, 'unknown'
    cached = usage.get('prompt_tokens_details', {})
    cached = cached.get('cached_tokens') if isinstance(cached, dict) else None
    inputs, outputs = Decimal(str(usage['prompt_tokens'])), Decimal(str(usage['completion_tokens']))
    input_rate, output_rate = Decimal(str(row['input_per_million'])), Decimal(str(row['output_per_million']))
    if row.get('cached_input_per_million') is not None:
        if not number(cached) or cached > inputs:
            return None, 'unknown_cache_usage'
        cached = Decimal(str(cached))
        total = (inputs - cached) * input_rate + cached * Decimal(str(row['cached_input_per_million']))
        method = 'tariff_with_cache'
    else:
        total, method = inputs * input_rate, 'tariff_uncached_assumption'
    return (total + outputs * output_rate) / Decimal(1000000), method


def _usage_measure(usages: list, key: str) -> dict:
    """Підсумовує відомі токени, явно відокремлюючи невідомі запити."""
    known = [u[key] for u in usages if u and number(u.get(key))]
    return {'known_sum': sum(known) if known else None, 'known_requests': len(known),
            'all_requests': len(usages), 'unknown_requests': len(usages) - len(known)}


def usage_metrics(runs: list, pricing: list) -> dict:
    """Обчислює usage/cost документів із повними даними та частковий відомий обсяг."""
    documents = [request_usages(run.data) for run in runs]
    usages = [u for doc in documents for u in doc]
    result = {key: _usage_measure(usages, key) for key in ('prompt_tokens', 'completion_tokens', 'total_tokens')}
    for key in ('prompt_tokens', 'completion_tokens'):
        sums = [sum(u[key] for u in doc) for doc in documents
                if all(u and number(u.get(key)) for u in doc)]
        result[key].update(mean_per_complete_document=sum(sums) / len(sums) if sums else None,
                           complete_documents=len(sums), all_documents=len(runs),
                           method='sum HTTP usage including retry/repair / complete documents')
    cached = [u.get('prompt_tokens_details', {}).get('cached_tokens') for u in usages
              if u and isinstance(u.get('prompt_tokens_details'), dict)]
    known_cached = [v for v in cached if number(v)]
    result['cached_tokens'] = {'known_sum': sum(known_cached) if known_cached else None,
                               'known_requests': len(known_cached), 'all_requests': len(usages)}
    prices = [[_request_cost(u, run.config, pricing) for u in doc] for run, doc in zip(runs, documents)]
    known = [value for doc in prices for value, _ in doc if value is not None]
    complete = [sum(v for v, _ in doc) for doc in prices if all(v is not None for v, _ in doc)]
    method_counts = {}
    for doc in prices:
        for _, method in doc:
            method_counts[method] = method_counts.get(method, 0) + 1
    result['cost'] = {'currency': 'USD', 'partial_known_cost': float(sum(known)) if known else None,
                      'priced_requests': len(known), 'all_requests': len(usages),
                      'complete_documents': len(complete), 'all_documents': len(runs),
                      'cost_per_1000_documents': float(sum(complete) / len(complete) * 1000) if complete else None,
                      'methods': method_counts, 'pricing': pricing,
                      'method': 'mean complete document cost * 1000; same token/cache distribution assumed',
                      'local_external_api_cost': 0 if all(r.config['provider'] == 'ollama' for r in runs) else None,
                      'local_hardware_electricity_cost': None}
    return result
