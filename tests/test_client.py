"""Офлайнова перевірка HTTP-запиту, timeout і політики повторів."""

import json
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest.mock import Mock

import httpx

from src.openrouter_client import ENDPOINT, OpenRouterClient, retry_delay
from tests.helpers import completion, settings


class ClientTests(unittest.TestCase):
    """Замінює OpenRouter підготовленими HTTP-відповідями через MockTransport.

    Справжня мережа недоступна тестованому клієнту. Вигаданий ключ потрібен
    лише для перевірки Authorization; паузи замінені Mock і не затримують тести.
    """

    def test_payload_timeout_and_response(self):
        """Перевіряє endpoint, ключ, timeout і точну структуру запиту.

        Початковий промпт і стаття мають потрапити в окремі повідомлення,
        strict-схема й sampling — в окремі параметри, без hidden golden data.
        """
        handler = Mock(return_value=httpx.Response(200, json=completion()))
        messages = [{'role': 'system', 'content': 'baseline'}, {'role': 'user', 'content': 'article'}]
        with httpx.Client(transport=httpx.MockTransport(handler)) as http:
            call = OpenRouterClient(settings(timeout_seconds=7), http).complete(messages)
        request = handler.call_args.args[0]
        payload = json.loads(request.content)
        self.assertEqual(str(request.url), ENDPOINT)
        self.assertEqual(request.headers['Authorization'], 'Bearer offline-test-key')
        self.assertEqual(request.extensions['timeout']['read'], 7)
        self.assertEqual(payload['messages'], messages)
        self.assertTrue(payload['response_format']['json_schema']['strict'])
        self.assertEqual(payload['provider'], {'require_parameters': True})
        self.assertEqual(payload['temperature'], 0)
        self.assertEqual(payload['top_p'], 1)
        self.assertNotIn('golden', payload)
        self.assertNotIn('api_key', payload)
        self.assertIsNone(call.error)
        self.assertEqual(len(call.requests), 1)

    def test_rate_limit_and_server_error_retry(self):
        """Імітує 429, потім 500 і успіх; перевіряє паузи та журнал усіх спроб.

        Retry-After=0 має переважати звичайну паузу, а наступна спроба
        використовує експоненційний backoff. Реального очікування немає.
        """
        handler = Mock(side_effect=[httpx.Response(429, headers={'Retry-After': '0'}),
                                    httpx.Response(500), httpx.Response(200, json=completion())])
        sleep = Mock()
        with httpx.Client(transport=httpx.MockTransport(handler)) as http:
            call = OpenRouterClient(settings(), http, sleep).complete([])
        self.assertIsNone(call.error)
        self.assertEqual([a['http_status'] for a in call.requests], [429, 500, 200])
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [0, 2])

    def test_authentication_and_bad_request_are_not_retried(self):
        """Перевіряє негайне завершення для постійних HTTP-помилок.

        Неправильні параметри, ключ, баланс, доступ чи маршрут не повинні
        витрачати наступні спроби й маскувати причину необмеженими повторами.
        """
        for status in (400, 401, 402, 403, 404):
            with self.subTest(status=status):
                handler = Mock(return_value=httpx.Response(status, json={'error': {'message': 'test'}}))
                sleep = Mock()
                with httpx.Client(transport=httpx.MockTransport(handler)) as http:
                    call = OpenRouterClient(settings(), http, sleep).complete([])
                self.assertEqual(handler.call_count, 1)
                self.assertIsNotNone(call.error)
                sleep.assert_not_called()

    def test_timeout_retry_and_exhaustion(self):
        """Імітує постійний ReadTimeout і перевіряє максимальну кількість спроб.

        За max_retries=1 мають відбутися рівно два HTTP-запити, після чого
        повертається помилка з журналом, без нескінченного повторення.
        """
        handler = Mock(side_effect=httpx.ReadTimeout('offline timeout'))
        with httpx.Client(transport=httpx.MockTransport(handler)) as http:
            call = OpenRouterClient(settings(max_retries=1), http, Mock()).complete([])
        self.assertEqual(handler.call_count, 2)
        self.assertEqual(len(call.requests), 2)
        self.assertIn('ReadTimeout', call.error)

    def test_long_retry_after_stops_without_early_retry(self):
        """Не дозволяє повторити запит раніше часу, вказаного сервером.

        Якщо Retry-After перевищив локальний ліміт, клієнт повертає помилку,
        не чекає довго й не скорочує серверну паузу до передчасного запиту.
        """
        handler = Mock(return_value=httpx.Response(429, headers={'Retry-After': '90'}))
        sleep = Mock()
        with httpx.Client(transport=httpx.MockTransport(handler)) as http:
            call = OpenRouterClient(settings(), http, sleep).complete([])
        self.assertEqual(handler.call_count, 1)
        self.assertIn('Retry-After', call.error)
        sleep.assert_not_called()

    def test_non_json_body_is_preserved(self):
        """Зберігає HTML або текст замість JSON у журналі невдалого запиту.

        Навіть HTTP 200 не вважається успішною відповіддю API, якщо немає
        JSON-об'єкта. Повторів такої генерації на транспортному рівні немає.
        """
        handler = Mock(return_value=httpx.Response(200, text='<html>failure</html>'))
        with httpx.Client(transport=httpx.MockTransport(handler)) as http:
            call = OpenRouterClient(settings(), http).complete([])
        self.assertIsNotNone(call.error)
        self.assertEqual(call.requests[0]['raw_body'], '<html>failure</html>')
        self.assertEqual(handler.call_count, 1)

    def test_retry_after_formats(self):
        """Перевіряє секунди, HTTP-дату та зіпсовані Retry-After без очікування.

        Невідомий формат використовує fallback, а дозволена HTTP-дата
        перетворюється на коротку невід'ємну паузу.
        """
        self.assertEqual(retry_delay('2', 1, 30), 2)
        self.assertEqual(retry_delay('invalid', 1, 30), 1)
        self.assertEqual(retry_delay('nan', 1, 30), 1)
        date = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=5), usegmt=True)
        self.assertGreaterEqual(retry_delay(date, 1, 30), 0)
        self.assertLessEqual(retry_delay(date, 1, 30), 5)
