"""Запис окремих звітів v2 без зміни inputs або старих evaluations."""

import json
from pathlib import Path


def display(metric: dict) -> str:
    """Показує чисельник/знаменник accuracy; undefined залишається unknown."""
    value = metric['value']
    return 'unknown' if value is None else f"{value:.1%} ({metric['numerator']}/{metric['denominator']})"


def render_comparison(summary: dict) -> str:
    """Будує читабельне порівняння тільки за фактичними JSON-метриками."""
    lines = ['# Порівняння Schema v2', '',
             f"Еталон: **{summary['annotation_status']}**. Політика: {summary['evaluator_policy_version']}.",
             'Якість і runtime нижче — тільки golden set; missing/invalid залишаються у знаменниках.', '',
             '| Експеримент | Primary N | Content | Aggregate | Valid/G | p50 / p95, с |',
             '| --- | --- | --- | --- | --- | --- |']
    for group in summary['groups']:
        runtime, quality, coverage = group['runtime'], group['quality'], group['coverage']
        latency = runtime['latency']
        lines.append(f"| {group['configuration']['experiment_id']} | {coverage['received_primary']}/{coverage['planned_primary']} "
                     f"| {display(quality['content_accuracy'])} | {display(quality['aggregate_accuracy'])} "
                     f"| {display(runtime['valid_over_golden'])} | {latency['p50']} / {latency['p95']} |")
    for group in summary['groups']:
        runtime, quality = group['runtime'], group['quality']
        latency = runtime['latency']
        lines.extend(['', f"## {group['configuration']['experiment_id']}", '',
                      '| Поле | Accuracy |', '| --- | --- |'])
        lines.extend(f'| {field} | {display(value)} |' for field, value in quality['field_accuracy'].items())
        for field, metrics in quality['lists'].items():
            lines.append(f"\n{field}: TP={metrics['tp']}, FP={metrics['fp']}, FN={metrics['fn']}; "
                         f"P={metrics['precision']['value']}, R={metrics['recall']['value']}, F1={metrics['f1']['value']}.")
        lines.append(f"\nLatency known n={latency['sample_count']}; cold start={latency['cold_start']}. "
                     'Токени, вартість та їх coverage див. summary.json → runtime.usage.')
    return '\n'.join(lines) + '\n'


def write_reports(output: Path, summary: dict, details: dict) -> None:
    """Записує summary останнім: збій запису не залишає маркера готового оцінювання.

    Exclusive creation захищає вже наявні файли навіть за конкурентного запису.
    Часткові файли після помилки не вважаються завершеним звітом.
    """
    output.mkdir(parents=True, exist_ok=True)
    payloads = [('details.json', json.dumps(details, ensure_ascii=False, indent=2, allow_nan=False)),
                ('comparison.md', render_comparison(summary)),
                ('summary.json', json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False))]
    for name, content in payloads:
        with (output / name).open('x', encoding='utf-8') as stream:
            stream.write(content + '\n')
