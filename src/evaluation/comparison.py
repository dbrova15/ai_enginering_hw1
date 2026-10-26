"""Відтворюване порівняння двох evaluator policies на незмінних входах і контролях."""

import json
from pathlib import Path

from src.evaluation.loading import read_json
from src.evaluation.models import EvaluationError, canonical_json, digest


def _controls(before: dict, after: dict) -> dict:
    """Перевіряє однакові контрольні факти й рахує реально виправлені FN та нові FP."""
    old = {c['id']: c for c in before['cases']}
    new = {c['id']: c for c in after['cases']}
    if len(old) != len(before['cases']) or len(new) != len(after['cases']) or old.keys() != new.keys():
        raise EvaluationError('Контролі до/після повинні мати ті самі унікальні ID.')
    for key in old:
        if {k: v for k, v in old[key].items() if k != 'actual'} != {k: v for k, v in new[key].items() if k != 'actual'}:
            raise EvaluationError(f'Контрольний факт змінився: {key}')
    positives = [key for key in old if old[key]['verdict'] == 'match']
    negatives = [key for key in old if key not in positives]
    fixed = [key for key in positives if old[key]['actual'] != 'match' and new[key]['actual'] == 'match']
    new_fp = [key for key in negatives if old[key]['actual'] != 'match' and new[key]['actual'] == 'match']
    return {'positive_count': len(positives), 'negative_count': len(negatives),
            'before_fn': sum(old[k]['actual'] != 'match' for k in positives),
            'after_fn': sum(new[k]['actual'] != 'match' for k in positives),
            'before_fp': sum(old[k]['actual'] == 'match' for k in negatives),
            'after_fp': sum(new[k]['actual'] == 'match' for k in negatives),
            'fixed_fn_ids': sorted(fixed), 'new_fp_ids': sorted(new_fp),
            'cases': [{'id': key, 'before': old[key]['actual'], 'after': new[key]['actual'],
                       'expected': new[key]['verdict']} for key in sorted(new)]}


def _verify_inputs(before: dict, after: dict) -> None:
    """Відхиляє порівняння змінених моделей/документів під виглядом зміни evaluator."""
    for key in ('inputs', 'sources'):
        if before['provenance'][key] != after['provenance'][key]:
            raise EvaluationError(f'Різні вхідні fingerprints: {key}')
    old, new = ({g['group_id']: g for g in s['groups']} for s in (before, after))
    if old.keys() != new.keys():
        raise EvaluationError('Різний набір конфігурацій evaluator до/після.')
    for key in old:
        for field in ('config', 'document_ids', 'golden_document_ids'):
            if canonical_json(old[key][field]) != canonical_json(new[key][field]):
                raise EvaluationError(f'Змінилася база порівняння: {field}')


def _metric_rows(old: dict, new: dict) -> list[dict]:
    """Вибирає однакові метрики й знаменники, не підміняючи фактично отримані нулі."""
    rows = []
    metrics = [('Components Identity F1', 'components', 'identity'),
               ('Components Full Fact F1', 'components', 'full_fact'),
               ('Technical Parameters F1', 'technical_parameters', 'full_fact')]
    for title, field, mode in metrics:
        rows.append({'metric': title, 'before': old['quality']['lists'][field][mode]['f1']['value'],
                     'after': new['quality']['lists'][field][mode]['f1']['value'], 'unit': 'ratio'})
    for field in ('main_subject', 'purpose'):
        rows.append({'metric': field + ' confirmed field accuracy',
                     'before': old['quality']['field_exact_accuracy'][field]['value'],
                     'after': new['quality']['field_exact_accuracy'][field]['value'], 'unit': 'ratio'})
    for metric, key in [('needs_review (atomic checks)', 'numerator')]:
        rows.append({'metric': metric, 'before': old['quality']['review']['needs_review'][key],
                     'after': new['quality']['review']['needs_review'][key], 'unit': 'count'})
    return rows


def _changed_examples(before: dict, after: dict) -> list:
    """Знаходить реальні нові підтвердження та review-пари з індексами доказів."""
    old_docs = {(g['group_id'], d['document_id']): d for g in before['groups'] for d in g['documents']}
    examples = []
    for group in after['groups']:
        for doc in group['documents']:
            previous = old_docs[(group['group_id'], doc['document_id'])]
            for field in ('components', 'technical_parameters'):
                old_pairs = {(p['expected_index'], p['predicted_index']): p
                             for p in previous['fields'][field].get('pairs', [])}
                for pair in doc['fields'][field].get('pairs', []):
                    key = (pair['expected_index'], pair['predicted_index'])
                    old = old_pairs.get(key)
                    kind = None
                    if pair['full_match'] and (old is None or not old['full_match']):
                        kind = 'new_full_fact_match'
                    elif pair.get('identity_confirmed') and old is None:
                        kind = 'new_identity_match'
                    elif pair.get('verdict') == 'needs_review' and old is None:
                        kind = 'new_review_candidate'
                    if kind:
                        examples.append({'group_id': group['group_id'], 'document_id': doc['document_id'],
                                         'field': field, 'kind': kind, 'pair': pair, 'run_path': doc['run_path']})
                new_identity = {(p['expected_index'], p['predicted_index'])
                                for p in doc['fields'][field].get('pairs', []) if p.get('identity_confirmed')}
                for key, pair in old_pairs.items():
                    if key not in new_identity:
                        examples.append({'group_id': group['group_id'], 'document_id': doc['document_id'],
                                         'field': field, 'kind': 'removed_identity_match',
                                         'pair': pair, 'run_path': doc['run_path']})
    return examples


def compare(before_dir: Path, after_dir: Path, controls_before: Path,
            controls_after: Path, output: Path) -> dict:
    """Створює до/після JSON і Markdown лише при однакових hashes/configs/контролях."""
    old, new = (read_json(p / 'summary.json') for p in (before_dir, after_dir))
    _verify_inputs(old, new)
    controls = _controls(read_json(controls_before), read_json(controls_after))
    old_groups = {g['group_id']: g for g in old['groups']}
    groups = [{'group_id': g['group_id'], 'model': g['config']['requested_model'],
               'metrics': _metric_rows(old_groups[g['group_id']], g),
               'fact_assessment': g['quality'].get('fact_assessment'),
               'review_checks_total': g['quality']['review']['total_checks']}
              for g in new['groups']]
    examples = _changed_examples(read_json(before_dir / 'details.json'), read_json(after_dir / 'details.json'))
    data = {'before_policy': old['provenance']['policy_version'], 'after_policy': new['provenance']['policy_version'],
            'inputs_equal': True, 'evaluation_status': new['evaluation_status'], 'groups': groups,
            'controls': controls, 'changed_examples': examples,
            'report_hashes': {str(p.resolve()): digest(p) for p in
                              (before_dir / 'summary.json', after_dir / 'summary.json', controls_before, controls_after)}}
    paths = [output / 'before_after.json', output / 'before_after.md']
    if any(p.exists() for p in paths):
        raise EvaluationError('Порівняльний звіт уже існує; перезапис заборонено.')
    bodies = [json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', render_comparison(data)]
    output.mkdir(parents=True, exist_ok=True)
    for path, body in zip(paths, bodies):
        with path.open('x', encoding='utf-8') as handle:
            handle.write(body)
    return data


def render_comparison(data: dict) -> str:
    """Показує зміни саме evaluator та обмеження, без обіцянки зростання всіх метрик."""
    lines = ['# Semantic matching: до та після', '',
             f"Статус: **{data['evaluation_status']}**. {data['before_policy']} → {data['after_policy']}.", '',
             'Golden set, TXT, промпт і відповіді моделей ідентичні за SHA-256. Моделі повторно не запускалися. '
             'Зміни нижче спричинені лише evaluator. Зростання F1 саме по собі не доводить виправлення.', '',
             '| Модель / метрика | Попередній оцінювач | Оновлений оцінювач |', '| --- | --- | --- |']
    for group in data['groups']:
        for row in group['metrics']:
            values = ['невідомо' if row[k] is None else f"{row[k]:.2%}" if row['unit'] == 'ratio'
                      else str(row[k]) for k in ('before', 'after')]
            lines.append(f"| {group['model']} / {row['metric']} | {' | '.join(values)} |")
    c = data['controls']
    lines += [f"| False negatives на {c['positive_count']} спільних позитивних контролях | {c['before_fn']} | {c['after_fn']} |",
              f"| False positives на {c['negative_count']} спільних негативних/review контролях | {c['before_fp']} | {c['after_fp']} |", '',
              'Контролі — синтетичні підтверджені факти, однакові для всіх моделей; це не частота помилок на корпусі. '
              'needs_review checks мають змінну кількість перевірок: їхнє число не є зіставною accuracy. '
              'Підтверджений переклад назви не скасовує неправильний model/manufacturer/role.', '',
              '## Виправлені false negatives на контролях', '',
              f"Підтверджено виправлено: **{len(c['fixed_fn_ids'])}**. Нових false positives: **{len(c['new_fp_ids'])}**.", '',
              ', '.join('`' + key + '`' for key in c['fixed_fn_ids']), '',
              '## Реальні зміни та невизначені випадки', '']
    for group in data['groups']:
        selected = [e for e in data['changed_examples'] if e['group_id'] == group['group_id']]
        # Показуємо окремо нові matches і кандидати, щоб review не видавався за виправлення.
        confirmed = [e for e in selected if e['kind'] in ('new_identity_match', 'new_full_fact_match')][:2]
        review = [e for e in selected if e['kind'] == 'new_review_candidate'][:2]
        removed = [e for e in selected if e['kind'] == 'removed_identity_match'][:2]
        for example in confirmed + review + removed:
            pair = example['pair']
            lines += [f"### {group['model']} / {example['document_id']} / {example['field']}", '',
                      f"{example['kind']}; expected[{pair['expected_index']}] ↔ predicted[{pair['predicted_index']}]; "
                      f"повний збіг: {pair['full_match']}; verdict: {pair.get('verdict')}.", '',
                      'Перевірки: ' + '; '.join(f"{check['check_id'].rsplit('.', 1)[-1]}={check['verdict']}"
                                                 for check in pair['checks']) + '.', '']
            if example['kind'] == 'removed_identity_match':
                lines += ['Це колишня пара, яку новий evaluator не підтверджує. Наведені checks належать '
                          'попередній політиці. Спільний код не доводить, що модуль і окремий чутливий '
                          'елемент — одна апаратна сутність; зниження identity F1 також потребує аналізу.', '']
        for field, facts in (group.get('fact_assessment') or {}).items():
            lines += [f"- {group['model']} / {field}: review-пар {facts['needs_review_pairs']}, "
                      f"неоднозначних груп {facts['ambiguous_groups']}, суперечностей еталону "
                      f"за підтвердженої identity {facts['confirmed_contradictions']}."]
    lines += ['', '## Висновок та обмеження достовірності', '',
              'Контрольні переклади, одиниці, діапазони й розміри розпізнаються без злиття негативних контролів. '
              'Це доказ на контрольному наборі, а не гарантія відсутності false positives на всіх документах. '
              'Непідтверджені subjects, невідомі терміни, часткові purpose та конфлікт HR-0207 лишаються review. '
              'Консервативні FP/FN включають такі факти, але не називають їх доведеними помилками моделі. '
              'Новий словник не виправляє вхідні атрибути та не доповнює їх зовнішніми знаннями.', '',
              'За наявними даними неможливо впевнено визначити кращу модель: еталони provisional, '
              'лише 10 документів, словник обмежений. Потрібна ручна перевірка кандидатів і дослідження '
              'помилок обох моделей за однією політикою. Контрольні позначки й обидва snapshots збережені.', '']
    return '\n'.join(lines)
