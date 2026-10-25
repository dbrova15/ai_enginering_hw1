"""Читання налаштувань запуску з .env та змінних оточення без розголошення ключа."""

import os
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OLLAMA_MODEL = 'llama3.2:3b'
DEFAULT_OLLAMA_BASE_URL = 'http://localhost:11434'
ENV_FIELDS = {
    'REQUEST_TIMEOUT_SECONDS': 'timeout_seconds', 'MAX_RETRIES': 'max_retries',
    'RETRY_BASE_SECONDS': 'retry_base_seconds',
    'MAX_RETRY_WAIT_SECONDS': 'max_retry_wait_seconds',
    'TEMPERATURE': 'temperature', 'TOP_P': 'top_p', 'MAX_TOKENS': 'max_tokens',
}


class ConfigError(ValueError):
    """Зрозуміла помилка налаштування, після якої запит не надсилається.

    Містить лише безпечне пояснення: назву відсутнього поля або порушене
    обмеження. Ключ чи повний вміст .env у повідомлення не включаються.
    """


class Settings(BaseModel):
    """Перевірені параметри одного запуску без жорстко заданої моделі.

    Ключ зберігається як SecretStr та не показується в repr об'єкта. Числові
    поля перевіряють межі й відхиляють нескінченність та NaN. max_retries —
    кількість додаткових HTTP-спроб, не враховуючи початковий запит чи repair.
    provider вибирає сервіс; api_key і model містять лише його активні значення.
    Без явного provider використовується openrouter для сумісності старих запусків.
    Створення цього об'єкта не викликає API й не змінює файлів.
    """

    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    provider: Literal['openrouter', 'openai', 'ollama'] = 'openrouter'
    api_key: SecretStr = Field(repr=False)
    model: str = Field(min_length=1)
    timeout_seconds: float = Field(default=60, gt=0, le=600)
    max_retries: int = Field(default=2, ge=0, le=10)
    retry_base_seconds: float = Field(default=1, gt=0, le=30)
    max_retry_wait_seconds: float = Field(default=30, gt=0, le=60)
    temperature: float = Field(default=0, ge=0, le=2)
    top_p: float = Field(default=1, gt=0, le=1)
    max_tokens: int = Field(default=4096, gt=0)
    ollama_base_url: AnyHttpUrl = Field(default=DEFAULT_OLLAMA_BASE_URL, validate_default=True)

    @field_validator('ollama_base_url')
    @classmethod
    def validate_ollama_base_url(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        """Перевіряє, що адреса Ollama є кореневою HTTP(S)-адресою сервера.

        Отримує вже розібраний URL і повертає його без змін. Відхиляє логін,
        пароль, параметри, фрагмент і шлях, оскільки клієнт сам додає
        /v1/chat/completions. Повідомлення про помилку не повторює введену адресу.
        Мережеве з'єднання під час цієї перевірки не встановлюється.
        """
        if value.username or value.password or value.query or value.fragment or value.path not in ('', '/'):
            raise ValueError('Вкажіть кореневу адресу Ollama без credentials, шляху, query чи fragment.')
        return value


def provider_fields(values: dict[str, str | None], provider: str) -> dict[str, str]:
    """Вибирає налаштування лише активного провайдера з уже прочитаних змінних.

    Для локальної Ollama повертає порожній ключ, задану або типову модель
    llama3.2:3b та адресу сервера. Для хмарних сервісів вимагає їхні ключ
    і модель, не підставляючи значень іншого провайдера. Файлів не читає;
    відсутні обов'язкові налаштування спричиняють безпечний ConfigError.
    """
    if provider == 'ollama':
        return {
            'api_key': '',
            'model': (values.get('OLLAMA_MODEL') or '').strip() or DEFAULT_OLLAMA_MODEL,
            'ollama_base_url': (values.get('OLLAMA_BASE_URL') or '').strip() or DEFAULT_OLLAMA_BASE_URL,
        }
    fields = {}
    for name in ('api_key', 'model'):
        variable = f'{provider.upper()}_{name.upper()}'
        fields[name] = (values.get(variable) or '').strip()
        if not fields[name]:
            raise ConfigError(f'Вкажіть {variable} у .env або змінних оточення.')
    return fields


def load_settings(env_path: Path = PROJECT_ROOT / '.env') -> Settings:
    """Читає .env, додає пріоритетні змінні процесу й повертає Settings.

    Отримує шлях до приватного .env; відсутній файл допустимий, якщо потрібні
    значення є в оточенні. LLM_PROVIDER вибирає тільки активні ключ і модель;
    локальна Ollama працює без API-ключа та має типову модель llama3.2:3b.
    Відсутній чи порожній LLM_PROVIDER означає openrouter. Не змінює os.environ
    і не створює .env. За відсутності активного ключа/моделі, невідомого
    провайдера або неправильних числових параметрів піднімає ConfigError
    без показу секретів. Значення-заглушка з .env.example не приймається.
    """
    values = {**dotenv_values(env_path, encoding='utf-8'), **os.environ}
    fields = {field: values[name] for name, field in ENV_FIELDS.items() if name in values}
    provider = (values.get('LLM_PROVIDER') or '').strip().lower() or 'openrouter'
    if provider not in ('openrouter', 'openai', 'ollama'):
        raise ConfigError('LLM_PROVIDER має бути openrouter, openai або ollama.')
    fields['provider'] = provider
    prefix = provider.upper()
    fields.update(provider_fields(values, provider))
    if fields['api_key'] in ('sk-or-...', 'sk-...'):
        raise ConfigError(f'Замініть приклад {prefix}_API_KEY справжнім ключем у .env.')
    if fields['model'].startswith('sk-'):
        raise ConfigError(f'{prefix}_MODEL має містити ID моделі, а не API-ключ.')
    try:
        return Settings.model_validate(fields)
    except ValidationError as exc:
        details = '; '.join(f"{error['loc'][0]}: {error['msg']}"
                            for error in exc.errors(include_input=False))
        raise ConfigError(f'Некоректні налаштування: {details}') from None
