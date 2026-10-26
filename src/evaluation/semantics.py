"""Доказові технічні поняття без fuzzy matching, зовнішніх знань або LLM.

Непокритий словником текст зберігає невизначеність. Порівняння числа не
використовується для ідентифікації пристрою чи призначення.
"""

import re

from src.evaluation.normalization import alias, schematic_model, stripped_context, text
from src.evaluation.policy import (ENTITY_CONCEPTS, PROPERTY_CONCEPTS, PROPERTY_FAMILIES,
                                   ROLE_CONCEPTS, STATEMENT_CONCEPTS)


def concept(value: str | None, dictionary: dict) -> str | None:
    """Повертає ID лише для повного відомого терміна; не видаляє невідомі уточнення."""
    normalized = text(value)
    return next((key for key, variants in dictionary.items() if normalized in variants), None)


def model_tokens(value: str | None) -> frozenset[str]:
    """Виділяє повні технічні коди; не змішує Uno/Mega чи R1 із моделлю виробу."""
    normalized = text(value) or ''
    codes = re.findall(r'(?<!\w)(?:[a-z]+\d[a-z0-9]*(?:-[a-z0-9]+)*|[a-z]+-\d[a-z0-9-]*)(?!\w)', normalized)
    codes = [v for v in codes if not re.fullmatch(r'(?:r|c|k|d|vt|q)\d+', v)]
    if re.search(r'\barduino\s+(uno|mega)\b', normalized):
        codes.append(re.search(r'\barduino\s+(uno|mega)\b', normalized)[1])
    return frozenset(codes)


def semantic_text(left: str | None, right: str | None, namespace: str = 'entity') -> str:
    """Зараховує доведений переклад; специфічний/невідомий залишок потребує перегляду."""
    if left is None or right is None:
        return 'match' if left == right else 'mismatch'
    if alias(left) == alias(right):
        return 'match'
    dictionary = {'entity': ENTITY_CONCEPTS, 'role': ROLE_CONCEPTS,
                  'purpose': STATEMENT_CONCEPTS}.get(namespace, ENTITY_CONCEPTS)
    a, b = concept(left, dictionary), concept(right, dictionary)
    if a and b:
        if {a, b} == {'arduino_uno', 'arduino_uno_rev3'}:
            return 'needs_review'
        return 'match' if a == b else 'mismatch'
    lm, rm = model_tokens(left), model_tokens(right)
    if lm and rm and lm != rm:
        return 'mismatch'
    return 'needs_review'


def property_evidence(name: str, subject: str | None) -> dict:
    """Ідентифікує властивість, не перетворюючи її назву в назву пристрою.

    Board + dimensions однозначно уточнює розміри плати. Якщо subject сам
    є Operating Voltage, це допомагає тільки властивості, але не subject evidence.
    """
    canonical = concept(stripped_context(name), PROPERTY_CONCEPTS)
    subject_property = concept(subject, PROPERTY_CONCEPTS)
    if canonical == 'dimensions' and concept(subject, ENTITY_CONCEPTS) == 'module_board':
        canonical = 'board_dimensions'
    if subject_property and canonical:
        if PROPERTY_FAMILIES.get(subject_property, subject_property) == PROPERTY_FAMILIES.get(canonical, canonical):
            canonical = subject_property
    return {'concept': canonical, 'text': stripped_context(name), 'subject_property': subject_property}


def compare_property(left: dict, right: dict) -> str:
    """Порівнює тип характеристики; родинні, але неповні терміни не дають match."""
    a, b = left['concept'], right['concept']
    if a and b:
        if a == b:
            return 'match'
        if PROPERTY_FAMILIES.get(a, a) == PROPERTY_FAMILIES.get(b, b):
            return 'needs_review'
        return 'mismatch'
    return 'match' if left['text'] == right['text'] else 'needs_review'


def subject_evidence(left: str | None, right: str | None) -> str:
    """Не підтверджує пристрій із порожнього subject або назви властивості."""
    if left is None or right is None:
        return 'needs_review'
    if concept(left, PROPERTY_CONCEPTS) or concept(right, PROPERTY_CONCEPTS):
        return 'needs_review'
    return semantic_text(left, right)


def component_weight(left: dict, right: dict) -> int:
    """Будує identity-доказ за сутністю/моделлю без злиття різних апаратних вузлів."""
    name_verdict = semantic_text(left['name'], right['name'])
    a, b = text(left['model']), text(right['model'])
    a, b = (value if _model_evidence(value) else None for value in (a, b))
    names_a, names_b = model_tokens(left['name']), model_tokens(right['name'])
    if names_a and names_b and names_a != names_b:
        return 0
    if name_verdict == 'mismatch':
        return 0
    if name_verdict == 'match':
        return 5
    if a and (a == b or _whole_model(a, right['name'])):
        return 4
    if b and _whole_model(b, left['name']):
        return 4
    return 0


def _model_evidence(value: str | None) -> bool:
    """Відсікає схемні позначення та загальні описи, які не доводять модель виробу."""
    plain_models = {'uno', 'mega', 'nicla vision', 'iot explorer kit'}
    if not value or schematic_model(value):
        return False
    code = re.search(r'\b(?:[a-z]+\d[a-z0-9]*|\d+[a-z][a-z0-9]*)\b', value)
    revision = re.fullmatch(r'(?:uno|mega)\s+rev\.\d+', value)
    return bool(code or revision or value in plain_models)


def _whole_model(model: str, name: str) -> bool:
    """Шукає весь код або багатослівну модель із межами слова, не ABC1 усередині ABC10.

    Це доказ identity з явної назви, а не виправлення окремого model-атрибута:
    неправильний/порожній model усе одно не проходить full_fact перевірку.
    """
    return bool(re.search(r'(?<!\w)' + re.escape(model) + r'(?!\w)', text(name) or ''))
