"""Багаторівневе підтвердження параметрів: предмет → властивість → величина/контекст."""

from src.evaluation.normalization import context_verdict
from src.evaluation.quantities import compare_quantity, quantity, unit
from src.evaluation.semantics import compare_property, property_evidence, subject_evidence

PROPERTY_DIMENSIONS = {
    'voltage': 'voltage', 'operating_voltage': 'voltage', 'supply_voltage': 'voltage',
    'input_voltage': 'voltage', 'output_voltage': 'voltage', 'voltage_drop': 'voltage',
    'current': 'current', 'current_consumption': 'current', 'board_dimensions': 'length',
    'threshold_angle': 'angle', 'angle_range': 'angle', 'capacitance': 'capacitance',
    'frequency': 'frequency', 'power': 'power',
}


def evidence(left: dict, right: dict) -> dict:
    """Збирає незалежні докази; значення не використовується для визначення предмета."""
    return {'subject': subject_evidence(left['subject'], right['subject']),
            'property': compare_property(property_evidence(left['name'], left['subject']),
                                         property_evidence(right['name'], right['subject']))}


def parameter_weight(left: dict, right: dict, candidate: bool = False) -> int:
    """Відокремлює доведені identity-пари від невизначених кандидатів.

    Невідомий subject дозволяє тільки review за відомою властивістю; доведені
    різні предмети/властивості не створюють пару через збіг числа.
    """
    proof = evidence(left, right)
    if 'mismatch' in proof.values():
        return 0
    if all(v == 'match' for v in proof.values()):
        return 5 if not candidate else 0
    known_property = property_evidence(left['name'], left['subject'])['concept']
    other_property = property_evidence(right['name'], right['subject'])['concept']
    return 1 if candidate and (proof['subject'] == 'match' or known_property and other_property) else 0


def _serial_quantity(value: dict) -> dict:
    """Зберігає точні Decimal як рядки, щоб деталізація не округлювала доказ."""
    return {k: [str(n) for n in v] if k == 'numbers' else v for k, v in value.items()}


def parameter_checks(prefix: str, left: dict, right: dict) -> list[dict]:
    """Повертає окремі перевірки кожного рівня з original/canonical доказами."""
    from src.evaluation.scoring import check

    proof = evidence(left, right)
    lq, rq = quantity(left['value'], left['unit']), quantity(right['value'], right['unit'])
    lu, ru = lq.get('dimension', unit(left['unit'])[0]), rq.get('dimension', unit(right['unit'])[0])
    context_left = ' '.join(str(left[k] or '') for k in ('subject', 'name', 'value'))
    context_right = ' '.join(str(right[k] or '') for k in ('subject', 'name', 'value'))
    return [
        check(prefix + '.subject', left['subject'], right['subject'], proof['subject'], 'semantic_subject'),
        check(prefix + '.name', left['name'], right['name'], proof['property'], 'semantic_property',
              property_evidence(left['name'], left['subject']), property_evidence(right['name'], right['subject'])),
        check(prefix + '.value', left['value'], right['value'], _value_verdict(left, right, lq, rq),
              'quantity_bounds_units', _serial_quantity(lq), _serial_quantity(rq)),
        check(prefix + '.unit', left['unit'], right['unit'], 'match' if lu == ru else 'mismatch',
              'effective_unit_dimension', lu, ru),
        check(prefix + '.context', context_left, context_right, context_verdict(context_left, context_right),
              'quantity_context'),
    ]


def _value_verdict(left: dict, right: dict, lq: dict, rq: dict) -> str:
    """Не зараховує непрозорий опис або фізично несумісний тип як підтверджене число.

    Наприклад, Board Size з V або Current Consumption = real-time monitoring
    потребує перегляду, навіть якщо обидва рядки однакові. Номер A4 дозволено
    порівнювати як конфігурацію, бо це не відома фізична величина з цієї таблиці.
    """
    for item, parsed in ((left, lq), (right, rq)):
        expected_dimension = PROPERTY_DIMENSIONS.get(property_evidence(item['name'], item['subject'])['concept'])
        if expected_dimension and parsed['kind'] != 'conflict':
            if parsed.get('dimension') != expected_dimension or parsed['kind'] == 'opaque':
                return 'needs_review'
    return compare_quantity(lq, rq)


def pair_verdict(checks: list[dict]) -> str:
    """Відділяє доведену суперечність від невизначеності та повного збігу факту."""
    verdicts = {c['verdict'] for c in checks}
    if 'mismatch' in verdicts:
        return 'mismatch'
    return 'needs_review' if 'needs_review' in verdicts else 'match'
