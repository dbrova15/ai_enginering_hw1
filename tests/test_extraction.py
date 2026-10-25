"""Перевірка завершення генерацій, валідації, repair та обліку спроб."""

import json
import unittest
from unittest.mock import Mock

import httpx

from src.extraction import extract_document
from src.openrouter_client import OpenRouterClient
from tests.helpers import completion, settings


def run_responses(responses: list[dict]) -> tuple[dict, Mock]:
    """Обробляє вигадану статтю послідовністю підроблених відповідей API.

    Повертає підсумок і mock-обробник для перевірки кількості та змісту запитів.
    Мережі, приватного .env і справжньої моделі немає; список responses задає
    точний сценарій початкової генерації та можливого repair.
    """
    handler = Mock(side_effect=[httpx.Response(200, json=body) for body in responses])
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        result = extract_document(OpenRouterClient(settings(), http, Mock()), 'baseline', 'article')
    return result, handler


class ExtractionTests(unittest.TestCase):
    """Перевіряє поведінку конвеєра на наперед відомих відповідях моделі.

    Відрізняє валідність першої спроби, успішне виправлення та failed, щоб
    майбутні метрики не приписували repair до первинної валідності.
    """

    def test_valid_first_response(self):
        """Валідний JSON має завершити обробку за один запит без repair.

        Перевіряє status, first_pass_valid, повернену модель й usage фікстури;
        це перевірка обліку, а не реальне вимірювання токенів чи точності.
        """
        result, handler = run_responses([completion()])
        self.assertEqual(result['status'], 'success')
        self.assertTrue(result['first_pass_valid'])
        self.assertEqual(handler.call_count, 1)
        self.assertEqual(result['attempts'][0]['returned_model'], 'test/returned-model')
        self.assertEqual(result['attempts'][0]['usage']['total_tokens'], 30)

    def test_single_repair_preserves_first_answer(self):
        """Імітує неправильний JSON, за яким іде правильний об'єкт.

        Очікує рівно один repair, збереження сирої першої відповіді та відмінний
        від success статус repaired. Початковий промпт і стаття не змінюються.
        """
        result, handler = run_responses([completion('not json'), completion()])
        self.assertEqual(result['status'], 'repaired')
        self.assertFalse(result['first_pass_valid'])
        self.assertEqual(result['retry_count'], 0)
        self.assertEqual(result['attempts'][0]['raw_content'], 'not json')
        payload = json.loads(handler.call_args.args[0].content)
        self.assertEqual([m['role'] for m in payload['messages']], ['system', 'user', 'assistant', 'user'])
        self.assertEqual(payload['messages'][0]['content'], 'baseline')
        self.assertEqual(payload['messages'][1]['content'], 'article')
        self.assertEqual(handler.call_count, 2)

    def test_two_invalid_answers_end_failed(self):
        """Зупиняє repair після другої невалідної відповіді.

        Зберігає обидві помилки та null замість результату; третього звернення
        до моделі бути не повинно, навіть якщо JSON синтаксично коректний.
        """
        result, handler = run_responses([completion('{}'), completion('{}')])
        self.assertEqual(result['status'], 'failed')
        self.assertIsNone(result['result'])
        self.assertEqual(handler.call_count, 2)
        self.assertTrue(all(a['error'] for a in result['attempts']))

    def test_refusal_and_truncated_generations_are_not_repaired(self):
        """Не намагається виправляти відмови або обірвані генерації.

        Перевіряє length, content_filter та явний refusal навіть за наявності
        схожого на валідний JSON; кожен сценарій завершується після одного запиту.
        """
        refusal = completion()
        refusal['choices'][0]['message']['refusal'] = 'test refusal'
        for body in [completion(finish_reason='length'), completion(finish_reason='content_filter'), refusal]:
            with self.subTest(body=body):
                result, handler = run_responses([body])
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(handler.call_count, 1)

    def test_api_errors_and_missing_envelope_are_failed(self):
        """Розпізнає помилку API всередині HTTP 200 та пошкоджений envelope.

        Вони не є JSON-помилками самого витягування, тому repair не виконується.
        Окремо перевіряє choice.error, відсутні choices, message та content.
        """
        choice_error = completion()
        choice_error['choices'][0]['error'] = {'code': 502}
        bodies = [{'error': {'code': 503}}, {}, {'choices': []},
                  {'choices': [{'message': None}]}, completion(), choice_error]
        bodies[4]['choices'][0]['message']['content'] = None
        for body in bodies:
            with self.subTest(body=body):
                result, handler = run_responses([body])
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(handler.call_count, 1)

    def test_missing_usage_stays_unknown(self):
        """Не підміняє відсутню статистику токенів нулями.

        Відповідь без usage може містити валідний результат, але її витрати
        залишаються невідомими; у журналі має бути null.
        """
        body = completion()
        del body['usage']
        result, _ = run_responses([body])
        self.assertIsNone(result['attempts'][0]['usage'])

    def test_transport_retry_count_excludes_repair(self):
        """Відрізняє повтор HTTP після 429 від нової repair-генерації.

        Сценарій: rate limit, невалідний JSON, успішний repair. Має бути
        три HTTP-спроби, дві генерації та тільки один транспортний retry.
        """
        handler = Mock(side_effect=[httpx.Response(429),
                                    httpx.Response(200, json=completion('{}')),
                                    httpx.Response(200, json=completion())])
        with httpx.Client(transport=httpx.MockTransport(handler)) as http:
            result = extract_document(OpenRouterClient(settings(), http, Mock()), 'baseline', 'article')
        self.assertEqual(result['status'], 'repaired')
        self.assertEqual(result['retry_count'], 1)
        self.assertEqual(len(result['attempts']), 2)
        self.assertEqual(handler.call_count, 3)
