"""Невеликі структури для передачі перевірених даних між модулями оцінювача."""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class EvaluationError(ValueError):
    """Зрозуміла помилка входів або режиму; CLI показує її без traceback."""


def canonical_json(value: Any) -> str:
    """Серіалізує дані стабільно, щоб порядок ключів не змінював ідентичність."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def digest(path: Path) -> str:
    """Рахує SHA-256 байтів файла, не змінюючи його вміст."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass
class RunRecord:
    """Збережений запуск із конфігурацією й результатом локальної перевірки.

    data містить початковий envelope. result доступний лише для придатного
    прогнозу; problems пояснює, чому даним не можна повністю довіряти.
    """

    path: Path
    data: dict
    config: dict
    result: dict | None
    first_valid: bool | None
    problems: list[str] = field(default_factory=list)

    @property
    def document_id(self) -> str:
        """Повертає перевірений ID документа для зіставлення з еталоном."""
        return self.data['document_id']

    @property
    def group_id(self) -> str:
        """Формує стабільний ID усієї конфігурації, включно з маршрутом API."""
        return hashlib.sha256(canonical_json(self.config).encode()).hexdigest()


@dataclass
class Dataset:
    """Входи одного оцінювання: еталони, групи запусків, метадані та застереження."""

    golden: dict[str, dict]
    groups: dict[str, list[RunRecord]]
    provenance: dict
    manifest: dict[str, dict]
    source_conflicts: dict[str, dict]
    warnings: list[str]
    provisional: bool
