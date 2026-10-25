"""Перевірка двох адаптерів, фабрики й спільної поведінки без API-викликів."""

import json
import unittest
from unittest.mock import Mock

import httpx

from src.chat_client import ApiCall, ChatCompletionsClient, retry_delay
from src.client_factory import create_client
from src.extraction import extract_document
from src.openai_client import ENDPOINT as OPENAI_ENDPOINT, OpenAIClient
from src.openrouter_client import ENDPOINT as ROUTER_ENDPOINT, OpenRouterClient
from tests.helpers import completion, settings


class ProviderClientTests(unittest.TestCase):
    """Перевіряє відмінності payload та однакову поведінку двох провайдерів.

    Клієнти працюють через MockTransport із вигаданим ключем і відповідями.
    Тести не завантажують .env, не звертаються до мережі й не витрачають коштів.
    """

    def test_factory_selects_default_and_openai(self):
        """Перевіряє тип клієнта без надсилання запитів.

        Старі Settings без provider створюють OpenRouter, а явний openai —
        OpenAI. Обидва об'єкти мають спільний транспорт і метод complete.
        """
        handler = Mock()
        with httpx.Client(transport=httpx.MockTransport(handler)) as http:
            default = create_client(settings(), http)
            direct = create_client(settings(provider='openai'), http)
            self.assertIsInstance(default, OpenRouterClient)
            self.assertIsInstance(direct, OpenAIClient)
            self.assertIsInstance(direct, ChatCompletionsClient)
        handler.assert_not_called()

    def test_openai_endpoint_auth_schema_and_token_limit(self):
        """Перевіряє прямий endpoint OpenAI та відсутність OpenRouter-only полів.

        Повідомлення, JSON Schema, sampling і timeout мають зберігатися,
        але MAX_TOKENS передається як max_completion_tokens. Ключ є лише
        в Authorization, не в JSON-тілі запиту.
        """
        handler = Mock(return_value=httpx.Response(200, json=completion()))
        messages = [{'role': 'system', 'content': 'baseline'}, {'role': 'user', 'content': 'article'}]
        config = settings(provider='openai', api_key='openai-only-key', model='openai-model',
                          max_tokens=777, temperature=0.4, top_p=0.9, timeout_seconds=9)
        with httpx.Client(transport=httpx.MockTransport(handler)) as http:
            call = create_client(config, http).complete(messages)
        request = handler.call_args.args[0]
        payload = json.loads(request.content)
        self.assertEqual(str(request.url), OPENAI_ENDPOINT)
        self.assertEqual(request.headers['Authorization'], 'Bearer openai-only-key')
        self.assertEqual(request.extensions['timeout']['read'], 9)
        self.assertEqual(payload['model'], 'openai-model')
        self.assertEqual(payload['messages'], messages)
        self.assertEqual(payload['max_completion_tokens'], 777)
        self.assertNotIn('max_tokens', payload)
        self.assertNotIn('provider', payload)
        self.assertNotIn('openai-only-key', request.content.decode())
        self.assertEqual(payload['temperature'], 0.4)
        self.assertEqual(payload['top_p'], 0.9)
        self.assertTrue(payload['response_format']['json_schema']['strict'])
        self.assertIsNone(call.error)

    def test_both_clients_retry_and_use_their_endpoints(self):
        """Для кожного провайдера імітує timeout, rate limit, потім успіх.

        Очікує три HTTP-спроби з однаковою політикою пауз, адресовані тільки
        обраному сервісу. Реальне очікування замінено Mock.
        """
        for provider, endpoint in [('openrouter', ROUTER_ENDPOINT), ('openai', OPENAI_ENDPOINT)]:
            with self.subTest(provider=provider):
                handler = Mock(side_effect=[httpx.ReadTimeout('test timeout'),
                                            httpx.Response(429, headers={'Retry-After': '0'}),
                                            httpx.Response(200, json=completion())])
                sleep = Mock()
                with httpx.Client(transport=httpx.MockTransport(handler)) as http:
                    client = create_client(settings(provider=provider), http)
                    client.sleep = sleep
                    call = client.complete([])
                self.assertIsNone(call.error)
                self.assertEqual(len(call.requests), 3)
                self.assertEqual([item.args[0] for item in sleep.call_args_list], [1, 0])
                self.assertTrue(all(str(item.args[0].url) == endpoint for item in handler.call_args_list))

    def test_openai_uses_same_single_repair(self):
        """Невалідна перша відповідь OpenAI має отримати одну repair-генерацію.

        Перевіряє облік first_pass_valid, status та збереження початкової
        відповіді. Конвеєр спільний і не має окремих правил для OpenAI.
        """
        handler = Mock(side_effect=[httpx.Response(200, json=completion('{}')),
                                    httpx.Response(200, json=completion())])
        with httpx.Client(transport=httpx.MockTransport(handler)) as http:
            result = extract_document(create_client(settings(provider='openai'), http), 'baseline', 'article')
        self.assertEqual(result['status'], 'repaired')
        self.assertFalse(result['first_pass_valid'])
        self.assertEqual(handler.call_count, 2)
        self.assertEqual(result['attempts'][0]['raw_content'], '{}')

    def test_openai_refusal_truncation_and_auth_are_not_repaired(self):
        """Перевіряє відмову, обрив і неправильний ключ на прямому OpenAI API.

        Кожен сценарій має завершитися failed після однієї HTTP-спроби,
        без перемикання провайдера, repair або повторів постійної помилки 401.
        """
        refusal = completion()
        refusal['choices'][0]['message']['refusal'] = 'test refusal'
        for response in [httpx.Response(200, json=refusal),
                         httpx.Response(200, json=completion(finish_reason='length')),
                         httpx.Response(401, json={'error': {'message': 'test'}})]:
            with self.subTest(status=response.status_code):
                handler = Mock(return_value=response)
                with httpx.Client(transport=httpx.MockTransport(handler)) as http:
                    result = extract_document(create_client(settings(provider='openai'), http), 'baseline', 'article')
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(handler.call_count, 1)

    def test_legacy_openrouter_imports_remain_available(self):
        """Підтверджує зворотну сумісність імпортів після виділення транспорту.

        Код, який раніше імпортував ApiCall чи retry_delay з openrouter_client,
        має отримувати ті самі об'єкти, що й новий спільний модуль.
        """
        from src.openrouter_client import ApiCall as LegacyCall, retry_delay as legacy_delay
        self.assertIs(LegacyCall, ApiCall)
        self.assertIs(legacy_delay, retry_delay)
