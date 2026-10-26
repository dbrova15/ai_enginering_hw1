"""Локальна модель Ollama через сумісний із Chat Completions HTTP-інтерфейс."""

import time
from collections.abc import Callable
from typing import Any

import httpx

from src.chat_client import ChatCompletionsClient
from src.config import Settings
from src.schemas import SCHEMA_V1, SchemaSpec


class OllamaClient(ChatCompletionsClient):
    """Викликає локальну модель, типово llama3.2:3b, без хмарного API-ключа.

    Використовує той самий формат повідомлень, JSON Schema, timeout і retry,
    що й інші адаптери. Відповідь choices/message/content перевіряється спільним
    конвеєром із Pydantic та однією repair-спробою. Модель і сервер мають бути
    встановлені та запущені заздалегідь; клієнт не завантажує й не запускає їх.
    """

    provider_name = 'Ollama'

    def __init__(
        self, settings: Settings, http_client: httpx.Client,
        sleep: Callable[[float], None] = time.sleep,
        *, schema_spec: SchemaSpec = SCHEMA_V1,
    ) -> None:
        """Зберігає залежності й формує endpoint із кореневої адреси Ollama.

        Отримує перевірені налаштування, відкритий HTTP-клієнт і спосіб паузи
        між повторними спробами. Додає /v1/chat/completions до OLLAMA_BASE_URL.
        Сам не виконує запитів; HTTP-клієнт закриває той, хто його створив.
        """
        super().__init__(settings, http_client, sleep, schema_spec=schema_spec)
        self.endpoint = str(settings.ollama_base_url).rstrip('/') + '/v1/chat/completions'

    def _headers(self) -> dict[str, str]:
        """Повертає порожній набір додаткових заголовків для локального сервера.

        Ollama не потребує API-ключа для цього локального маршруту. Навіть
        помилково переданий у Settings хмарний ключ не відправляється серверу.
        Метод не змінює налаштування й не виконує запитів.
        """
        return {}

    def _payload(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Готує запит із погодженою схемою та лімітом локальної генерації.

        Отримує повідомлення, повертає спільний payload з max_tokens, який
        сумісний endpoint Ollama перетворює на num_predict. temperature,
        top_p та JSON Schema передаються без зміни; параметрів OpenRouter
        чи max_completion_tokens тут немає. Мережа не викликається.
        """
        return {**super()._payload(messages), 'max_tokens': self.settings.max_tokens}
