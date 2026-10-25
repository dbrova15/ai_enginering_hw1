"""Офлайнова перевірка локальної Ollama: налаштування, HTTP, repair і звіт CLI."""

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import httpx

import main as cli
from src.client_factory import create_client
from src.config import ConfigError, load_settings
from src.extraction import extract_document
from src.ollama_client import OllamaClient
from tests.helpers import completion, settings


class OllamaConfigTests(unittest.TestCase):
    """Перевіряє локальні налаштування без читання справжнього .env.

    Використовує ізольоване оточення й тимчасові файли. Справжні ключі,
    сервер Ollama та встановлена модель для цих перевірок не потрібні.
    """

    def test_defaults_need_no_api_key(self):
        """Для LLM_PROVIDER=ollama використовує задану користувачем типову модель.

        Навіть якщо залишилися хмарні ключі або OLLAMA_API_KEY, активний ключ
        локального клієнта має бути порожнім. Модель і адреса мають безпечні
        локальні defaults, тому додаткових credentials не потрібно.
        """
        env = {'LLM_PROVIDER': ' Ollama ', 'OPENAI_API_KEY': 'unused-secret',
               'OPENROUTER_API_KEY': 'unused-secret', 'OLLAMA_API_KEY': 'unused-secret'}
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, env, clear=True):
            config = load_settings(Path(folder) / 'absent.env')
        self.assertEqual(config.provider, 'ollama')
        self.assertEqual(config.model, 'llama3.2:3b')
        self.assertEqual(str(config.ollama_base_url), 'http://localhost:11434/')
        self.assertEqual(config.api_key.get_secret_value(), '')

    def test_file_configuration_and_environment_precedence(self):
        """Читає локальну адресу й модель із .env з пріоритетом змінних процесу.

        Тимчасовий файл містить іншу модель, але значення OLLAMA_MODEL з
        оточення перемагає. Власна адреса сервера зберігається з файла.
        """
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '.env'
            path.write_text('LLM_PROVIDER=ollama\nOLLAMA_MODEL=other-model\n'
                            'OLLAMA_BASE_URL=http://127.0.0.1:12345/\n', encoding='utf-8')
            with patch.dict(os.environ, {'OLLAMA_MODEL': 'llama3.2:3b'}, clear=True):
                config = load_settings(path)
        self.assertEqual(config.model, 'llama3.2:3b')
        self.assertEqual(str(config.ollama_base_url), 'http://127.0.0.1:12345/')

    def test_empty_local_values_use_defaults(self):
        """Порожні або пробільні локальні значення повертають типову конфігурацію.

        Це дозволяє залишити необов'язкові поля прикладу незаповненими;
        скрипт усе одно використовує llama3.2:3b та localhost:11434.
        """
        env = {'LLM_PROVIDER': 'ollama', 'OLLAMA_MODEL': ' ', 'OLLAMA_BASE_URL': ''}
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, env, clear=True):
            config = load_settings(Path(folder) / 'absent.env')
        self.assertEqual(config.model, 'llama3.2:3b')
        self.assertEqual(str(config.ollama_base_url), 'http://localhost:11434/')

    def test_invalid_root_urls_are_rejected_without_echoing_credentials(self):
        """Відхиляє неправильний протокол, шлях та приховані параметри URL до мережі.

        Так клієнт не додає /v1 двічі та не бере секрет із credentials адреси.
        Помилки не повинні повторювати пароль або повний небезпечний URL.
        """
        urls = ['ftp://localhost:11434', 'http://localhost:11434/v1',
                'http://user:private-password@localhost:11434',
                'http://localhost:11434?key=private-password', 'not-a-url']
        with tempfile.TemporaryDirectory() as folder:
            for url in urls:
                env = {'LLM_PROVIDER': 'ollama', 'OLLAMA_BASE_URL': url}
                with self.subTest(url=url), patch.dict(os.environ, env, clear=True):
                    with self.assertRaises(ConfigError) as error:
                        load_settings(Path(folder) / 'absent.env')
                    self.assertNotIn('private-password', str(error.exception))

    def test_inactive_ollama_settings_do_not_change_cloud_provider(self):
        """Зіпсована локальна адреса не повинна впливати на типовий OpenRouter.

        Перевіряє попередню поведінку без LLM_PROVIDER та ізоляцію неактивних
        налаштувань: старий хмарний запуск залишається сумісним.
        """
        env = {'OPENROUTER_API_KEY': 'router-key', 'OPENROUTER_MODEL': 'router/model',
               'OLLAMA_BASE_URL': 'invalid', 'OLLAMA_MODEL': 'sk-invalid'}
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, env, clear=True):
            config = load_settings(Path(folder) / 'absent.env')
        self.assertEqual(config.provider, 'openrouter')
        self.assertEqual(config.model, 'router/model')


class OllamaClientTests(unittest.TestCase):
    """Перевіряє адаптер підробленими відповідями без локальної генерації.

    MockTransport гарантує, що тести не звертаються ні до Ollama, ні до
    хмарних API. Відповіді й usage є лише тестовими фікстурами.
    """

    def test_endpoint_schema_sampling_and_no_authorization(self):
        """Перевіряє endpoint, схему й sampling без передавання будь-якого ключа.

        Навіть якщо Settings створили вручну з ключем, OllamaClient не має
        надсилати Authorization. max_tokens використовується без полів інших API.
        """
        config = settings(provider='ollama', api_key='must-not-be-sent', model='llama3.2:3b',
                          ollama_base_url='http://127.0.0.1:12345/', max_tokens=512,
                          temperature=0.2, top_p=0.8)
        handler = Mock(return_value=httpx.Response(200, json=completion()))
        with httpx.Client(transport=httpx.MockTransport(handler)) as http:
            client = create_client(config, http)
            self.assertIsInstance(client, OllamaClient)
            call = client.complete([{'role': 'user', 'content': 'article'}])
        request = handler.call_args.args[0]
        payload = json.loads(request.content)
        self.assertEqual(str(request.url), 'http://127.0.0.1:12345/v1/chat/completions')
        self.assertNotIn('Authorization', request.headers)
        self.assertNotIn('must-not-be-sent', request.content.decode())
        self.assertEqual(payload['model'], 'llama3.2:3b')
        self.assertEqual(payload['temperature'], 0.2)
        self.assertEqual(payload['top_p'], 0.8)
        self.assertEqual(payload['max_tokens'], 512)
        self.assertNotIn('max_completion_tokens', payload)
        self.assertNotIn('provider', payload)
        self.assertEqual(payload['response_format']['type'], 'json_schema')
        self.assertFalse(payload['response_format']['json_schema']['schema']['additionalProperties'])
        self.assertIsNone(call.error)

    def test_single_repair_uses_common_pipeline(self):
        """Невалідний локальний JSON отримує тільки одну спробу виправлення.

        Перевіряє успішний repair і завершення failed після двох помилкових
        відповідей. Додаткового fallback до хмарного API не повинно бути.
        """
        for second, status in [(completion(), 'repaired'), (completion('{}'), 'failed')]:
            with self.subTest(status=status):
                handler = Mock(side_effect=[httpx.Response(200, json=completion('{}')),
                                            httpx.Response(200, json=second)])
                with httpx.Client(transport=httpx.MockTransport(handler)) as http:
                    result = extract_document(create_client(settings(provider='ollama', api_key=''), http), 'baseline', 'article')
                self.assertEqual(result['status'], status)
                self.assertFalse(result['first_pass_valid'])
                self.assertEqual(handler.call_count, 2)

    def test_unavailable_server_and_missing_model(self):
        """Обмежує повтори недоступного сервера й не повторює model-not-found 404.

        Не завантажує модель автоматично. В обох випадках повертає failed із
        журналом та без fallback на інший endpoint; паузи підмінені Mock.
        """
        for response, count in [(httpx.ConnectError('offline'), 2),
                                (httpx.Response(404, json={'error': {'message': 'model not found'}}), 1)]:
            handler = Mock(side_effect=response) if isinstance(response, Exception) else Mock(return_value=response)
            with self.subTest(attempts=count), httpx.Client(transport=httpx.MockTransport(handler)) as http:
                config = settings(provider='ollama', api_key='', max_retries=1)
                client = OllamaClient(config, http, sleep=Mock())
                result = extract_document(client, 'baseline', 'article')
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(handler.call_count, count)
            self.assertEqual(len(result['attempts']), 1)

    def test_cli_saves_local_provider_with_empty_secret(self):
        """Виконує main з Ollama й перевіряє JSON-звіт у тимчасовому каталозі.

        Ключ порожній, тому маскування не повинно змінити provider='ollama'
        чи назву моделі. Реальний .env і локальний сервер не використовуються.
        """
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            document, prompt = root / 'article.txt', root / 'v1.txt'
            document.write_text('article', encoding='utf-8')
            prompt.write_text('prompt', encoding='utf-8')
            handler = Mock(return_value=httpx.Response(200, json=completion()))
            http = httpx.Client(transport=httpx.MockTransport(handler))
            config = settings(provider='ollama', api_key='', model='llama3.2:3b')
            with patch('main.load_settings', return_value=config), \
                    patch('src.document_runner.httpx.Client', return_value=http), patch('sys.stdout', new_callable=io.StringIO):
                code = cli.main(['--document', str(document), '--prompt', str(prompt),
                                 '--output-dir', str(root / 'results')])
            report = json.loads(next((root / 'results').glob('*.json')).read_text(encoding='utf-8'))
        self.assertEqual(code, 0)
        self.assertEqual(report['provider'], 'ollama')
        self.assertEqual(report['requested_model'], 'llama3.2:3b')
        self.assertEqual(report['status'], 'success')
