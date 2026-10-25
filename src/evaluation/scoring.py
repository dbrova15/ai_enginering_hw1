"""Оцінка восьми полів: точні докази, окремі атрибути та явна невизначеність."""

from src.evaluation.matching import forced_pairs
from src.evaluation.models import canonical_json
from src.evaluation.normalization import alias, context_verdict, schematic_model, stripped_context, text
from src.evaluation.quantities import compare_quantity, quantity, unit

SCALARS = ('document_type', 'primary_topic', 'main_subject', 'purpose')
LISTS = ('components', 'technical_parameters', 'interfaces_protocols', 'software_tools')
FIELDS = (*SCALARS, *LISTS)


def check(check_id: str, expected, predicted, verdict: str, reason: str,
          canonical_expected=None, canonical_predicted=None) -> dict:
    """Зберігає один атомарний висновок із доказами й стабільним ID для аудиту."""
    return {'check_id': check_id, 'expected': expected, 'predicted': predicted,
            'verdict': verdict, 'reason_code': reason, 'rule_ids': [reason],
            'canonical_expected': canonical_expected, 'canonical_predicted': canonical_predicted}


def scalar(name: str, expected, predicted, kind: str = 'text') -> dict:
    """Порівнює scalar без зарахування непідтвердженого перефразування як match."""
    left, right = (expected, predicted) if kind == 'enum' else (alias(expected), alias(predicted))
    if left == right:
        verdict = 'match'
    elif expected is None or predicted is None or kind in ('enum', 'model', 'manufacturer'):
        verdict = 'mismatch'
    else:
        verdict = 'needs_review'
    if kind == 'model' and schematic_model(predicted):
        verdict = 'mismatch'
    return check(name, expected, predicted, verdict, 'scalar_' + kind, left, right)


def _groups(items: list[dict]) -> list[dict]:
    """Групує однакові об’єкти для matching, зберігаючи індекси та їхню кратність."""
    groups = {}
    for index, value in enumerate(items):
        key = canonical_json({k: text(v) for k, v in value.items()})
        group = groups.setdefault(key, {'value': value, 'indices': []})
        group['indices'].append(index)
    return [groups[key] for key in sorted(groups)]


def _weight(left: dict, right: dict, field: str) -> int:
    """Створює доказову пару за сутністю/subject; однакове число не є доказом."""
    if field == 'components':
        if alias(left['name']) == alias(right['name']):
            return 4
        model = text(left['model'])
        if model and not schematic_model(model):
            if model == text(right['model']):
                return 5
            if model in (text(right['name']) or ''):
                return 3
        return 0
    subject_match = alias(left['subject']) == alias(right['subject'])
    name_match = stripped_context(left['name']) == stripped_context(right['name'])
    return 4 if subject_match and name_match else 0


def _parameter_checks(prefix: str, left: dict, right: dict) -> list[dict]:
    """Перевіряє всі частини характеристики, не приховуючи втрату межі чи статусу."""
    lq, rq = quantity(left['value'], left['unit']), quantity(right['value'], right['unit'])
    verdict = compare_quantity(lq, rq)
    checks = [scalar(prefix + '.subject', left['subject'], right['subject']),
              scalar(prefix + '.name', stripped_context(left['name']), stripped_context(right['name']))]
    # Числовий масштаб уже враховано у value; unit тут перевіряє розмірність.
    lu, ru = unit(left['unit']), unit(right['unit'])
    unit_verdict = 'match' if lu[0] == ru[0] else 'mismatch'
    if left['unit'] is None or right['unit'] is None:
        unit_verdict = 'match' if left['unit'] == right['unit'] else 'mismatch'
    checks += [check(prefix + '.value', left['value'], right['value'], verdict,
                     'quantity_bounds_units', _serial_quantity(lq), _serial_quantity(rq)),
               check(prefix + '.unit', left['unit'], right['unit'], unit_verdict,
                     'unit_dimension', lu[0], ru[0])]
    lc = ' '.join(str(left[k] or '') for k in ('subject', 'name', 'value'))
    rc = ' '.join(str(right[k] or '') for k in ('subject', 'name', 'value'))
    checks.append(check(prefix + '.context', lc, rc, context_verdict(lc, rc), 'quantity_context'))
    return checks


def _serial_quantity(value: dict) -> dict:
    """Представляє Decimal текстом для прозорого JSON без похибки float."""
    return {k: [str(n) for n in v] if k == 'numbers' else v for k, v in value.items()}


def _pair_checks(field: str, left: dict, right: dict, prefix: str, conflict: dict | None) -> list:
    """Створює атрибутні перевірки пари; source conflict ніколи не дає model TP."""
    if field == 'technical_parameters':
        return _parameter_checks(prefix, left, right)
    checks = [scalar(prefix + '.' + key, left[key], right[key], kind)
              for key, kind in [('name', 'text'), ('model', 'model'),
                                ('manufacturer', 'manufacturer'), ('role', 'text')]]
    if conflict and text(right['model']) in conflict['models']:
        model_check = checks[1]
        model_check.update(verdict='needs_review', reason_code='source_conflict',
                           rule_ids=['source_conflict'], evidence=conflict)
    return checks


def object_list(field: str, expected: list, predicted: list, conflict: dict | None = None) -> dict:
    """Оцінює identity і повні факти, зберігаючи FP дублікатів та альтернативні пари."""
    gold, pred = _groups(expected), _groups(predicted)
    edges = {(i, j): weight for i, g in enumerate(gold) for j, p in enumerate(pred)
             if (weight := _weight(g['value'], p['value'], field))}
    matching = forced_pairs(len(gold), len(pred), edges)
    checks, pairs = [], []
    for i, j in matching['pairs']:
        gi, pi = gold[i]['indices'][0], pred[j]['indices'][0]
        prefix = f'{field}[{gi}:{pi}]'
        identity = check(prefix + '.identity', gold[i]['value'], pred[j]['value'],
                         'match', 'identity_evidence')
        attributes = _pair_checks(field, gold[i]['value'], pred[j]['value'], prefix, conflict)
        checks.extend([identity, *attributes])
        pairs.append({'expected_index': gi, 'predicted_index': pi, 'checks': attributes,
                      'full_match': all(c['verdict'] == 'match' for c in attributes)})
    used_g = {pair['expected_index'] for pair in pairs}
    used_p = {pair['predicted_index'] for pair in pairs}
    missing = [i for i in range(len(expected)) if i not in used_g]
    extras = [i for i in range(len(predicted)) if i not in used_p]
    _unpaired_checks(field, gold, pred, matching, missing, extras, checks)
    duplicate_gold = [g['indices'] for g in gold if len(g['indices']) > 1]
    if duplicate_gold:
        checks.append(check(field + '.gold_duplicates', duplicate_gold, None,
                            'needs_review', 'duplicate_golden_objects'))
    strict_tp = sum(pair['full_match'] for pair in pairs)
    return {'exact': strict_tp == len(expected) == len(predicted) and not duplicate_gold,
            'pairs': pairs, 'checks': checks, 'missing': missing, 'extra_predicted': extras,
            'identity': counts(len(pairs), len(expected), len(predicted)),
            'full_fact': counts(strict_tp, len(expected), len(predicted)),
            'duplicate_golden': duplicate_gold,
            'duplicate_predicted': [g['indices'] for g in pred if len(g['indices']) > 1],
            'ambiguous_pairing_groups': _review_groups(matching['review_edges'])}


def _review_groups(edges: list) -> list[list]:
    """Об’єднує пов’язані неоднозначні ребра, щоб одна проблема не рахувалася двічі."""
    groups = []
    for i, j in edges:
        nodes = {('g', i), ('p', j)}
        touching = [g for g in groups if g & nodes]
        for group in touching:
            nodes |= group
            groups.remove(group)
        groups.append(nodes)
    return [sorted(group) for group in groups]


def _unpaired_checks(field, gold, pred, matching, missing, extras, checks) -> None:
    """Додає по одному check для review-групи або доведеного незакритого елемента."""
    review_g, review_p = set(), set()
    for number, group in enumerate(_review_groups(matching['review_edges'])):
        review_g.update(gold[i]['indices'][0] for kind, i in group if kind == 'g')
        review_p.update(pred[i]['indices'][0] for kind, i in group if kind == 'p')
        checks.append(check(f'{field}.pairing.{number}', group, None, 'needs_review', 'ambiguous_pairing'))
    for side, indices, reviewed in [('missing', missing, review_g), ('extra_predicted', extras, review_p)]:
        original = {index: group['value'] for group in (gold if side == 'missing' else pred)
                    for index in group['indices']}
        for index in indices:
            if index not in reviewed:
                item = check(f'{field}.{side}.{index}', original[index] if side == 'missing' else None,
                             original[index] if side != 'missing' else None, 'mismatch', side)
                item['expected_index' if side == 'missing' else 'predicted_index'] = index
                checks.append(item)


def counts(tp: int, gold: int, pred: int) -> dict:
    """Повертає базові цілі лічильники, з яких однозначно обчислюються PR/F1."""
    return {'tp': tp, 'fn': gold - tp, 'fp': pred - tp, 'expected': gold, 'predicted': pred}


def string_list(field: str, expected: list, predicted: list) -> dict:
    """Порівнює множини одного поля, не зараховуючи збіг у сусідній категорії."""
    left, right = {alias(v, field) for v in expected}, {alias(v, field) for v in predicted}
    checks = [check(f'{field}.{index}', v if v in left else None, v if v in right else None,
                    'match' if v in left & right else 'mismatch', 'set_membership')
              for index, v in enumerate(sorted(left | right))]
    return {'exact': left == right, 'checks': checks, 'missing': sorted(left - right),
            'extra_predicted': sorted(right - left), 'full_fact': counts(len(left & right), len(left), len(right)),
            'duplicate_predicted_count': len(predicted) - len(right),
            'duplicate_golden_count': len(expected) - len(left)}


def score_document(expected: dict, predicted: dict | None, conflict: dict | None = None) -> dict:
    """Оцінює всі вісім полів, включно з відсутнім чи невалідним прогнозом."""
    result = {}
    for field in FIELDS:
        gold = expected[field]
        if predicted is None:
            item = {'exact': False, 'checks': [check(field, gold, None, 'unavailable_prediction',
                                                      'unavailable_prediction')]}
            if field in LISTS:
                size = len(set(alias(v, field) for v in gold)) if field.endswith(('protocols', 'tools')) else len(gold)
                item.update(full_fact=counts(0, size, 0), missing=list(range(size)), extra_predicted=[])
                if field == 'components':
                    item['identity'] = counts(0, size, 0)
        elif field in SCALARS:
            c = scalar(field, gold, predicted[field], 'enum' if field in SCALARS[:2] else 'text')
            item = {'exact': c['verdict'] == 'match', 'checks': [c]}
        elif field in LISTS[:2]:
            item = object_list(field, gold, predicted[field], conflict)
        else:
            item = string_list(field, gold, predicted[field])
        result[field] = item
    return result
