"""Адаптер прямого OpenAI Chat Completions API з погодженою JSON Schema."""

from typing import Any

from src.chat_client import ChatCompletionsClient


ENDPOINT = 'https://api.openai.com/v1/chat/completions'


class OpenAIClient(ChatCompletionsClient):
    """Надсилає статтю безпосередньо до OpenAI, минаючи OpenRouter.

    Отримує активні ключ і модель через Settings. Успадковує timeout,
    обмежені HTTP-повтори та журнал зі спільного транспорту, тому конвеєр
    валідації й repair працює однаково для обох провайдерів. Сам конструктор
    не викликає мережу; HTTP-клієнт закриває той, хто його створив.
    """

    endpoint = ENDPOINT
    provider_name = 'OpenAI'

    def _payload(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Доповнює спільний запит лімітом генерації, прийнятим OpenAI.

        Отримує system/user та можливі repair-повідомлення, повертає JSON-тіло
        зі strict-схемою й max_completion_tokens зі спільного MAX_TOKENS.
        Не додає OpenRouter-параметр provider і не містить ключа. Sampling
        передається явно; несумісність обраної моделі повернеться помилкою API,
        а не прихованою зміною налаштувань. Метод не робить мережевих запитів.
        """
        return {**super()._payload(messages),
                'max_completion_tokens': self.settings.max_tokens}
