"""Адаптер OpenRouter: маршрутизація та параметри поверх спільного HTTP-клієнта."""

from typing import Any

from src.chat_client import ApiCall, ChatCompletionsClient, retry_delay


ENDPOINT = 'https://openrouter.ai/api/v1/chat/completions'
__all__ = ['ApiCall', 'OpenRouterClient', 'retry_delay', 'ENDPOINT']


class OpenRouterClient(ChatCompletionsClient):
    """Надсилає повідомлення до OpenRouter зі strict-схемою й перевіркою параметрів.

    Зберігає попередній конструктор і формат запиту. Спільна основа виконує
    HTTP, timeout, повтори й журналювання, а цей адаптер визначає лише адресу
    та параметри OpenRouter. Створення об'єкта ще не звертається до мережі;
    HTTP-клієнт закриває той, хто його створив.
    """

    endpoint = ENDPOINT
    provider_name = 'OpenRouter'

    def _payload(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Додає до спільного JSON-запиту специфічні параметри OpenRouter.

        Отримує готові повідомлення й повертає тіло запиту з max_tokens та
        provider.require_parameters. Останній вимагає маршрут із підтримкою
        переданих параметрів. Ключ у тіло не додається; API тут не викликається.
        Формат запиту залишається сумісним із попереднім OpenRouter-клієнтом.
        """
        return {**super()._payload(messages), 'max_tokens': self.settings.max_tokens,
                'provider': {'require_parameters': True}}
