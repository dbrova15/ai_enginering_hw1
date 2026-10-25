"""Офлайнове збереження файлів і повний шлях запуску через main."""

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import httpx

import main as cli
from src.config import ConfigError
from src.result_writer import save_result
from tests.helpers import completion, settings


class WriterTests(unittest.TestCase):
    """Перевіряє звіти лише в тимчасових каталогах без приватних даних.

    Звичайні результати проєкту не змінюються. Після кожного тесту створені
    файли видаляються стандартним TemporaryDirectory.
    """

    def test_unique_unicode_files_and_recursive_redaction(self):
        """Перевіряє UTF-8, унікальні імена та маскування ключа на всіх рівнях.

        Два записи мають створити два файли без перезапису. Секрет не повинен
        залишитися в рядках, списках чи ключах словників; вихідні дані зберігаються.
        """
        secret = 'private-offline-key'
        data = {'name': 'Датчик', 'nested': [{secret: f'echo {secret}'}]}
        with tempfile.TemporaryDirectory() as folder:
            first = save_result(data, Path(folder) / 'results', secret)
            second = save_result(data, Path(folder) / 'results', secret)
            self.assertNotEqual(first, second)
            text = first.read_text(encoding='utf-8')
            self.assertNotIn(secret, text)
            self.assertIn('Датчик', text)
            self.assertEqual(json.loads(text)['nested'][0]['[REDACTED]'], 'echo [REDACTED]')
            self.assertIn(secret, data['nested'][0])


class CliTests(unittest.TestCase):
    """Проганяє main із тимчасовими файлами та повністю підробленим HTTP.

    load_settings замінено тестовими налаштуваннями: реальний .env не читається.
    Перевіряє не лише окремі функції, а й файл результату та exit code програми.
    """

    def test_successful_run_saves_metadata_and_prompt_hash(self):
        """Виконує повний успішний запуск без мережі та перевіряє збережений звіт.

        Підтверджує ID зі шляху документа, точний хеш байтів промпту, sampling,
        usage, returned_model, тривалість та результат зі статусом success.
        """
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            document = root / 'TEST-1.txt'
            prompt = root / 'v1.txt'
            document.write_text('Тестова стаття про датчик.', encoding='utf-8')
            prompt.write_bytes(b'baseline\r\nexact')
            handler = Mock(return_value=httpx.Response(200, json=completion()))
            http = httpx.Client(transport=httpx.MockTransport(handler))
            with patch('main.load_settings', return_value=settings()), \
                    patch('src.document_runner.httpx.Client', return_value=http), patch('sys.stdout', new_callable=io.StringIO):
                code = cli.main(['--document', str(document), '--prompt', str(prompt),
                                 '--output-dir', str(root / 'results')])
            report = json.loads(next((root / 'results').glob('*.json')).read_text(encoding='utf-8'))
        self.assertEqual(code, 0)
        self.assertEqual(report['document_id'], 'TEST-1')
        self.assertEqual(report['status'], 'success')
        self.assertEqual(report['prompt']['sha256'], hashlib.sha256(b'baseline\r\nexact').hexdigest())
        self.assertEqual(report['requested_model'], 'test/model')
        self.assertEqual(report['provider'], 'openrouter')
        self.assertEqual(report['attempts'][0]['returned_model'], 'test/returned-model')
        self.assertEqual(report['sampling'], {'temperature': 0, 'top_p': 1})
        self.assertGreaterEqual(report['latency_seconds'], 0)
        self.assertNotIn('offline-test-key', json.dumps(report))

    def test_openai_cli_writes_provider_and_masks_active_key(self):
        """Виконує main з активним OpenAI та перевіряє маршрут і записаний provider.

        Відповідь навмисно віддзеркалює вигаданий ключ у службовому полі.
        У звіті він має бути замаскований, а в запиті — переданий тільки
        прямому endpoint OpenAI. Реальний .env та мережа не використовуються.
        """
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            document = root / 'article.txt'
            prompt = root / 'v1.txt'
            document.write_text('article', encoding='utf-8')
            prompt.write_text('prompt', encoding='utf-8')
            body = {**completion(), 'test_echo': 'active-openai-secret'}
            handler = Mock(return_value=httpx.Response(200, json=body))
            http = httpx.Client(transport=httpx.MockTransport(handler))
            config = settings(provider='openai', api_key='active-openai-secret', model='openai-model')
            with patch('main.load_settings', return_value=config), \
                    patch('src.document_runner.httpx.Client', return_value=http), patch('sys.stdout', new_callable=io.StringIO):
                code = cli.main(['--document', str(document), '--prompt', str(prompt),
                                 '--output-dir', str(root / 'results')])
            text = next((root / 'results').glob('*.json')).read_text(encoding='utf-8')
            report = json.loads(text)
        self.assertEqual(code, 0)
        self.assertEqual(report['provider'], 'openai')
        self.assertEqual(report['requested_model'], 'openai-model')
        self.assertNotIn('active-openai-secret', text)
        self.assertEqual(str(handler.call_args.args[0].url), 'https://api.openai.com/v1/chat/completions')

    def test_failed_api_still_saves_report_and_nonzero_exit(self):
        """Імітує 401 й перевіряє збереження невдалого запуску з кодом 1.

        Не повинно бути ні repair, ні повторного HTTP-запиту. Повідомлення
        сервера з віддзеркаленим вигаданим ключем має бути замасковане у файлі.
        """
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            document = root / 'article.txt'
            prompt = root / 'v1.txt'
            document.write_text('article', encoding='utf-8')
            prompt.write_text('prompt', encoding='utf-8')
            handler = Mock(return_value=httpx.Response(401, json={'error': 'offline-test-key'}))
            http = httpx.Client(transport=httpx.MockTransport(handler))
            with patch('main.load_settings', return_value=settings()), \
                    patch('src.document_runner.httpx.Client', return_value=http), patch('sys.stdout', new_callable=io.StringIO):
                code = cli.main(['--document', str(document), '--prompt', str(prompt),
                                 '--output-dir', str(root / 'results')])
            text = next((root / 'results').glob('*.json')).read_text(encoding='utf-8')
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(text)['status'], 'failed')
        self.assertNotIn('offline-test-key', text)
        self.assertEqual(handler.call_count, 1)

    def test_missing_and_empty_document_never_calls_api(self):
        """Зупиняє запуск до мережі, якщо стаття відсутня або порожня.

        Обидва сценарії повертають код 2 й безпечне повідомлення замість
        traceback. HTTP-клієнт не повинен навіть створюватися.
        """
        with tempfile.TemporaryDirectory() as folder:
            absent = Path(folder) / 'absent.txt'
            empty = Path(folder) / 'empty.txt'
            empty.write_text('  \n', encoding='utf-8')
            for path in (absent, empty):
                with self.subTest(path=path.name), patch('main.load_settings', return_value=settings()), \
                        patch('src.document_runner.httpx.Client') as http, patch('sys.stderr', new_callable=io.StringIO):
                    self.assertEqual(cli.main(['--document', str(path)]), 2)
                    http.assert_not_called()

    def test_bad_configuration_never_calls_api(self):
        """Відсутність обов'язкових налаштувань зупиняє запуск до читання статті.

        Перевіряє код 2, показ зрозумілого ConfigError і відсутність HTTP;
        реального .env у цьому сценарії немає.
        """
        with patch('main.load_settings', side_effect=ConfigError('Вкажіть OPENROUTER_MODEL.')), \
                patch('src.document_runner.httpx.Client') as http, patch('sys.stderr', new_callable=io.StringIO) as error:
            self.assertEqual(cli.main([]), 2)
        http.assert_not_called()
        self.assertIn('OPENROUTER_MODEL', error.getvalue())

    def test_help_never_loads_configuration_or_calls_api(self):
        """Показ довідки завершується кодом 0 без .env та мережі.

        Це дозволяє безпечно ознайомитися з аргументами перед налаштуванням
        ключа й обранням моделі.
        """
        with patch('main.load_settings') as config, patch('src.document_runner.httpx.Client') as http, \
                patch('sys.stdout', new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as exit_status:
                cli.main(['--help'])
        self.assertEqual(exit_status.exception.code, 0)
        config.assert_not_called()
        http.assert_not_called()
