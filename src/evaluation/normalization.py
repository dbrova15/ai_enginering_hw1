"""Безпечна нормалізація тексту, моделей і контексту без нечіткого пошуку."""

import re
import unicodedata

from src.evaluation.policy import ALIASES, CONTEXT_MARKERS


def text(value: str | None) -> str | None:
    """Уніфікує регістр і пробіли, залишає технічні знаки всередині рядка.

    null залишається null. Не видаляє плюси C++, знаки нерівності, крапки
    версій або дефіси моделей, тому різні технічні позначення не зливаються.
    """
    if value is None:
        return None
    result = unicodedata.normalize('NFC', value).casefold()
    result = result.translate(str.maketrans({'’': "'", '‘': "'", '“': '"', '”': '"'}))
    return re.sub(r'\s+', ' ', result).strip().strip(' ,;:!?"\'«»').rstrip('.')


def alias(value: str | None, namespace: str = 'entity') -> str | None:
    """Застосовує тільки перелічені у policy еквівалентності конкретного поля."""
    normalized = text(value)
    for canonical, variants in ALIASES.get(namespace, {}).items():
        if normalized in variants:
            return canonical
    return normalized


def context(value: str | None) -> tuple[str, ...]:
    """Знаходить явні статуси характеристики; не виводить measured з числа."""
    normalized = text(value) or ''
    return tuple(sorted(key for key, variants in CONTEXT_MARKERS.items()
                        if any(re.search(r'(?<!\w)' + re.escape(v), normalized) for v in variants)))


def context_verdict(expected: str, predicted: str) -> str:
    """Розрізняє явну суперечність статусів і відсутність потрібного контексту."""
    left, right = context(expected), context(predicted)
    if left == right:
        return 'match'
    return 'mismatch' if left and right else 'needs_review'


def stripped_context(value: str | None) -> str | None:
    """Відокремлює відомі статуси; для UA/RU приймає лише задокументовані основи.

    Видалений маркер не губиться: context_verdict незалежно перевіряє його
    в початкових subject/name/value. Загального стемінгу назв тут немає.
    """
    result = text(value)
    if result is None:
        return None
    for variants in CONTEXT_MARKERS.values():
        for word in variants:
            ending = r'\w*' if not word.isascii() else ''
            result = re.sub(r'\b' + re.escape(word) + ending + r'\b', '', result)
    return alias(re.sub(r'\s+', ' ', result).strip())


def schematic_model(value: str | None) -> bool:
    """Визначає схемні позначення R1/C1/K1, які не є моделлю виробу."""
    return bool(value and re.fullmatch(r'(?:r|c|k|d|vt|q)\d+', text(value) or ''))
