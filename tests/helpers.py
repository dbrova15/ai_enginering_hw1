"""Невеликі тестові дані для перевірок без зовнішньої моделі."""

import json

from src.config import Settings


def settings(**overrides) -> Settings:
    """Створює налаштування з вигаданими ключем і моделлю для офлайнових тестів.

    Іменовані overrides замінюють окремі значення, наприклад кількість retry.
    .env не читається; об'єкт сам не створює HTTP-запитів.
    """
    return Settings(**{'api_key': 'offline-test-key', 'model': 'test/model', **overrides})


def valid_result() -> dict:
    """Повертає новий мінімальний об'єкт із усіма вісьмома полями схеми.

    Nullable-поля заповнені null, списки порожні. Кожен тест отримує окремий
    словник і може змінювати його, не пошкоджуючи даних інших перевірок.
    """
    return {
        'document_type': 'tutorial', 'primary_topic': 'devices_automation',
        'main_subject': None, 'purpose': None, 'components': [],
        'technical_parameters': [], 'interfaces_protocols': [], 'software_tools': [],
    }


def completion(content: str | None = None, finish_reason: str = 'stop') -> dict:
    """Будує вигадану відповідь OpenRouter для MockTransport.

    Приймає текст відповіді та причину завершення. Без тексту серіалізує
    valid_result. Usage заданий лише як тестова фікстура, не реальне вимірювання.
    Жодних мережевих викликів не виконує.
    """
    return {
        'id': 'offline-generation', 'model': 'test/returned-model',
        'choices': [{'finish_reason': finish_reason,
                     'message': {'role': 'assistant', 'content': content if content is not None
                                 else json.dumps(valid_result())}}],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 20, 'total_tokens': 30},
    }
