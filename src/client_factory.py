"""Вибір активного адаптера за перевіреним налаштуванням LLM_PROVIDER."""

import httpx

from src.chat_client import ChatCompletionsClient
from src.config import Settings
from src.openai_client import OpenAIClient
from src.ollama_client import OllamaClient
from src.schemas import SCHEMA_V1, SchemaSpec
from src.openrouter_client import OpenRouterClient


def create_client(settings: Settings, http_client: httpx.Client,
                  *, schema_spec: SchemaSpec = SCHEMA_V1) -> ChatCompletionsClient:
    """Створює клієнт одного провайдера без виклику моделі.

    Отримує перевірені Settings та відкритий HTTP-клієнт. Для provider=openai
    повертає OpenAIClient, для openrouter — OpenRouterClient, для ollama —
    локальний OllamaClient. Конфігурація
    перевіряє допустимі значення раніше; тут немає fallback на іншого
    провайдера або читання його ключа. Життєвий цикл HTTP-клієнта не змінює.
    """
    clients = {'openrouter': OpenRouterClient, 'openai': OpenAIClient, 'ollama': OllamaClient}
    return clients[settings.provider](settings, http_client, schema_spec=schema_spec)
