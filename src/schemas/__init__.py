"""Єдиний реєстр версій для payload, локальної валідації та журналу запуску."""

import hashlib
import json
from dataclasses import dataclass

from pydantic import BaseModel

from src.schemas.v1 import ExtractionResult
from src.schemas.v2 import ExtractionResultV2


@dataclass(frozen=True)
class SchemaSpec:
    """Незмінний descriptor контракту; не викликає API й не читає налаштувань.

    Локальні validators дублювання не додають unsupported keywords до API
    schema: їх усе одно обов’язково перевіряє Pydantic після відповіді.
    """

    version: str
    model: type[BaseModel]
    api_name: str

    @property
    def api_schema(self) -> dict:
        """Повертає актуальний структурний контракт вибраної Pydantic-моделі."""
        return self.model.model_json_schema()

    @property
    def sha256(self) -> str:
        """Хешує саме структурну JSON Schema стабільно щодо порядку ключів."""
        encoded = json.dumps(self.api_schema, sort_keys=True, ensure_ascii=False).encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()


SCHEMA_V1 = SchemaSpec('v1', ExtractionResult, 'hardware_extraction')
SCHEMA_V2 = SchemaSpec('v2', ExtractionResultV2, 'hardware_extraction_v2')


def get_schema(version: str = 'v1') -> SchemaSpec:
    """Обирає лише відомий контракт; невідома версія зупиняє запуск до мережі."""
    if version not in ('v1', 'v2'):
        raise ValueError('Невідома версія схеми; допустимі v1 або v2.')
    return SCHEMA_V1 if version == 'v1' else SCHEMA_V2
