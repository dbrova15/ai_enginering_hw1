"""Розбір фізичних величин через Decimal зі збереженням меж і приблизності."""

import re
from decimal import Decimal

from src.evaluation.normalization import text

NUMBER = r'[+-]?\d+(?:[.,]\d+)?(?:[eE][+-]?\d+)?'
UNITS = {
    'V': ('voltage', '1'), 'В': ('voltage', '1'),
    'A': ('current', '1'), 'А': ('current', '1'),
    'mA': ('current', '.001'), 'мА': ('current', '.001'),
    'uA': ('current', '.000001'), 'µA': ('current', '.000001'),
    'μA': ('current', '.000001'), 'мкА': ('current', '.000001'),
    'F': ('capacitance', '1'), 'mF': ('capacitance', '.001'),
    'uF': ('capacitance', '.000001'), 'µF': ('capacitance', '.000001'),
    'μF': ('capacitance', '.000001'), 'мкФ': ('capacitance', '.000001'),
    'kg': ('mass', '1'), 'g': ('mass', '.001'), 'кг': ('mass', '1'),
    'm': ('length', '1'), 'cm': ('length', '.01'), 'mm': ('length', '.001'),
    'м': ('length', '1'), 's': ('time', '1'), 'ms': ('time', '.001'),
    'с': ('time', '1'), 'h': ('time', '3600'), 'год': ('time', '3600'),
    'Hz': ('frequency', '1'), 'kHz': ('frequency', '1000'),
    'MHz': ('frequency', '1000000'), 'W': ('power', '1'),
    '°C': ('temperature', '1'), '%': ('percent', '1'), 'px': ('pixels', '1'),
    '°': ('angle', '1'), 'см': ('length', '.01'),
    'мм': ('length', '.001'),
}
UNIT_WORDS = {
    'v': 'V', 'в': 'В', 'volt': 'V', 'volts': 'V',
    'ampere': 'A', 'amperes': 'A', 'microampere': 'uA', 'microamperes': 'uA',
    'meter': 'm', 'meters': 'm', 'metre': 'm', 'metres': 'm',
    'kilogram': 'kg', 'kilograms': 'kg', 'kilo': 'kg', 'kilos': 'kg',
    'second': 's', 'seconds': 's', 'pixels': 'px',
    'degree': '°', 'degrees': '°', 'градус': '°', 'градуси': '°',
    'градусів': '°', 'градусов': '°', 'градусы': '°',
    'centimeter': 'cm', 'centimeters': 'cm', 'centimetres': 'cm',
    'millimeter': 'mm', 'millimeters': 'mm',
}


def unit(value: str | None) -> tuple[str | None, Decimal, bool]:
    """Повертає розмірність, масштаб і факт розпізнавання; зберігає SI-регістр."""
    if value is None:
        return None, Decimal(1), True
    cleaned = value.strip()
    canonical = cleaned if cleaned in UNITS else UNIT_WORDS.get(cleaned.casefold(), cleaned)
    if canonical in UNITS:
        dimension, factor = UNITS[canonical]
        return dimension, Decimal(factor), True
    return text(value), Decimal(1), False


def _expression(value: str) -> str:
    """Перетворює тільки явні словесні обмеження на символи, не змінюючи числа."""
    value = value.strip().replace('−', '-').replace('≥', '>=').replace('≤', '<=')
    value = re.sub(r'\b(?:a dozen|dozen)\b', '12', value, flags=re.IGNORECASE)
    for words, symbol in [
        (r'at least|щонайменше|не менше', '>='),
        (r'at most|не більше|up to|до', '<='),
        (r'under|less than|менше', '<'), (r'more than|більше', '>'),
        (r'about|approximately|приблизно', '~'),
    ]:
        value = re.sub(r'^(?:' + words + r')\s+', symbol, value, flags=re.IGNORECASE)
    return value


def quantity(value: str, declared_unit: str | None) -> dict:
    """Будує порівнювану величину або повертає непрозорий запис для перегляду.

    Не вгадує одиниці за пристроєм. Конфлікт між одиницею в value та unit
    позначає явно. Кілька чисел без відомої структури не стають одним числом.
    """
    parts = re.split(r'\s*[xх×*]\s*', value, flags=re.IGNORECASE)
    if len(parts) > 1:
        return _dimensions(value, parts, declared_unit)
    return _scalar_quantity(value, declared_unit)


def _dimensions(original: str, parts: list[str], declared_unit: str | None) -> dict:
    """Порівнює впорядковані розміри, не перетворюючи їх на площу чи сортований набір."""
    # Загальна одиниця в кінці поширюється на всі осі лише коли вона явна.
    suffix = re.fullmatch(r'.*\d\s*([A-Za-zµμА-Яа-я°%]+)', parts[-1])
    shared = declared_unit or (suffix[1] if suffix else None)
    axes = [_scalar_quantity(p, shared) for p in parts]
    if any(axis['kind'] == 'conflict' for axis in axes):
        return {'kind': 'conflict', 'original': original, 'unit': declared_unit}
    if len(parts) in (2, 3) and all(a['kind'] == '=' and a['dimension'] == 'length' for a in axes):
        return {'kind': 'dimensions', 'numbers': [a['numbers'][0] for a in axes], 'dimension': 'length'}
    return {'kind': 'opaque', 'value': text(original), 'unit': text(declared_unit)}


def _scalar_quantity(value: str, declared_unit: str | None) -> dict:
    """Розбирає одну вісь/число/діапазон, зберігаючи первинну перевірку одиниць."""
    expression = _expression(value)
    dimension, scale, known = unit(declared_unit)
    suffix = re.fullmatch(r'(.*\d)\s*([A-Za-zµμА-Яа-я°%]+)', expression)
    if suffix:
        embedded = unit(suffix[2])
        if embedded[2]:
            if declared_unit is not None and embedded[:2] != (dimension, scale):
                return {'kind': 'conflict', 'original': value, 'unit': declared_unit}
            dimension, scale, known = embedded
            expression = suffix[1].strip()
    if re.search(r'\d,\d{3}(?:\D|$)', expression):
        return {'kind': 'opaque', 'value': text(value), 'unit': text(declared_unit)}
    bounds = re.fullmatch(rf'\s*({NUMBER})\s*(?:–|—|to|\.\.|-)\s*({NUMBER})\s*', expression)
    single = re.fullmatch(rf'\s*(<=|>=|<|>|~|≈)?\s*({NUMBER})\s*', expression)
    if not known or not (bounds or single):
        return {'kind': 'opaque', 'value': text(value), 'unit': text(declared_unit)}
    if bounds:
        numbers = [Decimal(v.replace(',', '.')) * scale for v in bounds.groups()]
        if numbers[0] > numbers[1]:
            return {'kind': 'conflict', 'original': value, 'unit': declared_unit}
        return {'kind': 'range', 'numbers': numbers, 'dimension': dimension}
    operator = single[1] or '='
    operator = '~' if operator == '≈' else operator
    return {'kind': operator, 'numbers': [Decimal(single[2].replace(',', '.')) * scale],
            'dimension': dimension}


def compare_quantity(left: dict, right: dict) -> str:
    """Зараховує лише доведені числові еквівалентності без довільної tolerance."""
    if 'conflict' in (left['kind'], right['kind']):
        return 'mismatch'
    if 'opaque' in (left['kind'], right['kind']):
        return 'match' if left == right else 'needs_review'
    return 'match' if left == right else 'mismatch'
