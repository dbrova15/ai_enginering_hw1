"""Спільний HTTP-транспорт Chat Completions: схема, timeout і обмежені retry."""

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from src.config import Settings
from src.schema import ExtractionResult


@dataclass
class ApiCall:
    """Підсумок одного звернення до моделі з усіма транспортними повторами.

    response містить JSON-відповідь API, якщо її вдалося отримати, а requests —
    журнал кожної HTTP-спроби з часом і сирим результатом. error пояснює збій
    транспорту або HTTP. Цей контейнер сам нічого не надсилає й не записує.
    """

    response: dict[str, Any] | None
    requests: list[dict[str, Any]]
    error: str | None = None


def retry_delay(header: str | None, fallback: float, maximum: float) -> float | None:
    """Обирає дозволену паузу перед повтором за заголовком Retry-After.

    Отримує заголовок із секундами чи HTTP-датою, резервну паузу та межу
    очікування. Повертає секунди або None, якщо сервер вимагає чекати довше
    межі. Неправильний заголовок замінює резервною паузою; сама не засинає.
    """
    delay = fallback
    if header:
        try:
            delay = float(header)
        except ValueError:
            try:
                target = parsedate_to_datetime(header)
                if target.tzinfo is None:
                    target = target.replace(tzinfo=timezone.utc)
                delay = (target - datetime.now(timezone.utc)).total_seconds()
            except (ValueError, TypeError, OverflowError):
                delay = fallback
    if not math.isfinite(delay):
        delay = fallback
    delay = max(0, delay)
    return delay if delay <= maximum else None


class ChatCompletionsClient:
    """Спільна основа HTTP-клієнтів OpenRouter, OpenAI та Ollama зі strict-схемою.

    Відповідає лише за HTTP, timeout та повтори; не оцінює факти й не виконує
    repair невалідного витягування. HTTP-клієнт передається ззовні, тому в
    тестах мережу можна повністю замінити. Закривати його має той, хто створив.
    """

    endpoint: str
    provider_name: str

    def __init__(
        self, settings: Settings, http_client: httpx.Client,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Зберігає конфігурацію, HTTP-клієнт і спосіб очікування між спробами.

        Запитів ще не робить. У звичайному запуску sleep призупиняє програму,
        у тестах його замінюють функцією без очікування. Ключ використовується
        тільки для Authorization і не додається до журналу налаштувань.
        """
        self.settings = settings
        self.http_client = http_client
        self.sleep = sleep

    def _payload(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Створює тіло запиту з повідомлень і погодженої Pydantic-схеми.

        Повертає словник для JSON без API-ключа та provider-specific полів.
        Адаптери додають лише власний ліміт токенів і параметри маршрутизації.
        Метод нічого не надсилає й не додає еталонів чи міток маніфесту.
        """
        return {
            'model': self.settings.model, 'messages': messages, 'stream': False,
            'temperature': self.settings.temperature, 'top_p': self.settings.top_p,
            'response_format': {
                'type': 'json_schema',
                'json_schema': {
                    'name': 'hardware_extraction', 'strict': True,
                    'schema': ExtractionResult.model_json_schema(),
                },
            },
        }

    def _headers(self) -> dict[str, str]:
        """Повертає заголовок авторизації для хмарного API.

        Бере тільки активний ключ із перевірених налаштувань. Він не потрапляє
        до JSON-тіла або журналу. Локальний адаптер Ollama перевизначає цей
        метод, щоб узагалі не передавати Authorization. Запит тут не виконується.
        """
        return {'Authorization': f'Bearer {self.settings.api_key.get_secret_value()}'}

    def _send_once(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Виконує рівно одну HTTP-спробу та повертає її журнал.

        Передає ключ у заголовку й обмежує мережеве очікування timeout.
        Зберігає HTTP-код, тривалість, JSON або нерозібраний текст відповіді.
        Транспортні помилки перетворює на безпечний опис без traceback і ключа.
        Повторів, repair і запису файлів цей метод не робить.
        """
        started = time.perf_counter()
        attempt: dict[str, Any] = {'http_status': None, 'response': None, 'error': None}
        try:
            response = self.http_client.post(
                self.endpoint, json=payload, timeout=self.settings.timeout_seconds,
                headers=self._headers(),
            )
            attempt['http_status'] = response.status_code
            attempt['retry_after'] = response.headers.get('Retry-After')
            try:
                attempt['response'] = response.json()
            except ValueError:
                attempt['raw_body'] = response.text
        except httpx.RequestError as exc:
            attempt['error'] = f'Мережева помилка: {type(exc).__name__}'
        attempt['latency_seconds'] = time.perf_counter() - started
        return attempt

    def complete(self, messages: list[dict[str, str]]) -> ApiCall:
        """Отримує відповідь API, обмежено повторюючи тимчасові збої.

        Вхід — готові system/user/assistant повідомлення. Вихід — ApiCall із
        журналом усіх HTTP-спроб. Повторює мережеві помилки, 408, 429 та 5xx,
        але не помилки ключа, балансу чи схеми. Пауза росте експоненційно;
        Retry-After має пріоритет. Коли спроби вичерпані, повертає error,
        а не запускає нескінченний цикл. Один repair викликає цей метод окремо.
        """
        attempts = []
        payload = self._payload(messages)
        for index in range(self.settings.max_retries + 1):
            attempt = self._send_once(payload)
            attempts.append(attempt)
            status = attempt['http_status']
            if status is not None and 200 <= status < 300:
                body = attempt['response']
                if isinstance(body, dict):
                    return ApiCall(body, attempts)
                return ApiCall(None, attempts, f'{self.provider_name} повернув відповідь не у форматі JSON-об’єкта.')
            temporary = status is None or status in (408, 429) or status >= 500
            error = attempt['error'] or f'{self.provider_name} повернув HTTP {status}.'
            if not temporary or index == self.settings.max_retries:
                return ApiCall(None, attempts, error)
            fallback = min(self.settings.retry_base_seconds * 2 ** index,
                           self.settings.max_retry_wait_seconds)
            delay = retry_delay(attempt.get('retry_after'), fallback,
                                self.settings.max_retry_wait_seconds)
            if delay is None:
                return ApiCall(None, attempts, 'Retry-After перевищує дозволений час очікування.')
            self.sleep(delay)
        raise RuntimeError('Недосяжний стан циклу повторів.')
