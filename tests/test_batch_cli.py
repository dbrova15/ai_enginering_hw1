"""Офлайнова перевірка --all-documents, підготовки файлів і часткових помилок."""

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import httpx

import main as cli
from src.document_runner import InputFileError, prepare_documents
from tests.helpers import completion, settings


def exercise_batch(files: dict[str, str | bytes], responses: list[httpx.Response]) -> dict:
    """Виконує пакетний CLI на тимчасовому наборі файлів і підробленому API.

    files задає відносні шляхи й вміст, responses — очікувані HTTP-відповіді.
    Повертає exit code, текст консолі, JSON-звіти та mock-обробник для перевірок.
    Справжній .env не читається, мережа не використовується; усі файли й
    HTTP-клієнти очищаються після тесту, включно з достроковою зупинкою черги.
    """
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        texts, output, prompt = root / 'texts', root / 'results', root / 'v1.txt'
        texts.mkdir()
        output.mkdir()
        previous = output / 'previous.json'
        previous.write_text('{"preserve":true}', encoding='utf-8')
        prompt.write_text('baseline', encoding='utf-8')
        for name, value in files.items():
            path = texts / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value if isinstance(value, bytes) else value.encode('utf-8'))
        handler = Mock(side_effect=responses)
        count = sum(Path(name).suffix.lower() == '.txt' for name in files)
        clients = [httpx.Client(transport=httpx.MockTransport(handler)) for _ in range(count)]
        try:
            with patch('main.TEXTS_ROOT', texts), patch('main.load_settings', return_value=settings(max_retries=0)), \
                    patch('src.document_runner.httpx.Client', side_effect=clients) as factory, \
                    patch('sys.stdout', new_callable=io.StringIO) as stdout, \
                    patch('sys.stderr', new_callable=io.StringIO) as stderr:
                code = cli.main(['--all-documents', '--prompt', str(prompt), '--output-dir', str(output)])
            reports = [json.loads(path.read_text(encoding='utf-8')) for path in output.glob('run_*.json')]
            return {'code': code, 'stdout': stdout.getvalue(), 'stderr': stderr.getvalue(),
                    'reports': reports, 'handler': handler, 'factory_calls': factory.call_count,
                    'previous': previous.read_text(encoding='utf-8')}
        finally:
            for client in clients:
                client.close()


class BatchCliTests(unittest.TestCase):
    """Перевіряє пакетну поведінку, не запускаючи оплачуваних генерацій.

    Тимчасовий корпус і MockTransport дозволяють перевірити порядок, окремі
    результати, фінальні лічильники та поведінку помилок незалежно від моделі.
    """

    def test_recursive_order_separate_results_and_old_file_preserved(self):
        """Обробляє три мови рекурсивно, ігноруючи інші розширення.

        Перевіряє стабільний порядок за шляхами, окремий запит і звіт для
        кожної статті, прогрес та збереження старого файла результату.
        """
        result = exercise_batch({'uk/C.txt': 'article C', 'en/A.txt': 'article A',
                                 'ru/B.TXT': 'article B', 'notes.json': '{}'},
                                [httpx.Response(200, json=completion()) for _ in range(3)])
        self.assertEqual(result['code'], 0)
        self.assertEqual(len(result['reports']), 3)
        self.assertEqual({r['document_id'] for r in result['reports']}, {'A', 'B', 'C'})
        sent = [json.loads(call.args[0].content)['messages'] for call in result['handler'].call_args_list]
        self.assertEqual([messages[1]['content'] for messages in sent], ['article A', 'article B', 'article C'])
        self.assertTrue(all(messages[0]['content'] == 'baseline' for messages in sent))
        self.assertIn('[1/3] A.txt', result['stdout'])
        self.assertIn('success=3', result['stdout'])
        self.assertEqual(result['previous'], '{"preserve":true}')

    def test_conflicting_selection_is_rejected_before_configuration(self):
        """Забороняє одночасні --document та --all-documents ще в argparse.

        Повертається код 2 без читання .env чи створення HTTP-клієнта;
        випадковий запуск у двох режимах не може спричинити витрати.
        """
        with patch('main.load_settings') as config, patch('sys.stderr', new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as error:
                cli.main(['--document', 'article.txt', '--all-documents'])
        self.assertEqual(error.exception.code, 2)
        config.assert_not_called()

    def test_empty_corpus_fails_before_http(self):
        """Порожній каталог або каталог лише з не-TXT файлами не викликає API.

        Користувач отримує пояснення відсутності документів і код 2,
        замість успішного підсумку з нульовою кількістю текстів.
        """
        for files in ({}, {'notes.json': '{}'}):
            with self.subTest(files=files):
                result = exercise_batch(files, [])
                self.assertEqual(result['code'], 2)
                self.assertEqual(result['factory_calls'], 0)
                self.assertIn('немає TXT', result['stderr'])

    def test_bad_later_file_prevents_all_api_calls(self):
        """Перевіряє весь набір до запиту навіть за помилки в останньому файлі.

        Порожній текст або неправильний UTF-8 не повинні дозволяти оплатити
        обробку попередніх статей до виявлення локальної проблеми.
        """
        for bad in ('  \n', b'\xff\xfe'):
            with self.subTest(bad=repr(bad)):
                result = exercise_batch({'A.txt': 'valid', 'Z.txt': bad}, [])
                self.assertEqual(result['code'], 2)
                self.assertEqual(result['handler'].call_count, 0)
                self.assertEqual(result['reports'], [])

    def test_failed_validation_continues_and_returns_nonzero(self):
        """Дві невалідні відповіді для першої статті не блокують другу.

        Невдала стаття зберігається як failed, наступна — як success.
        Підсумок має бути повним, але exit code 1 повідомляє про частковий збій.
        """
        result = exercise_batch({'A.txt': 'first', 'B.txt': 'second'},
                                [httpx.Response(200, json=completion('{}')),
                                 httpx.Response(200, json=completion('{}')),
                                 httpx.Response(200, json=completion())])
        self.assertEqual(result['code'], 1)
        self.assertEqual(result['handler'].call_count, 3)
        self.assertEqual({r['document_id']: r['status'] for r in result['reports']},
                         {'A': 'failed', 'B': 'success'})
        self.assertIn('failed=1', result['stdout'])
        self.assertIn('не оброблено=0', result['stdout'])

    def test_repaired_result_has_separate_counter(self):
        """Успішний repair не зараховується до success із першої спроби.

        Запуск завершується кодом 0, але фінальний підсумок розрізняє
        success=0 і repaired=1; обидві генерації збережені у звіті.
        """
        result = exercise_batch({'A.txt': 'article'},
                                [httpx.Response(200, json=completion('{}')),
                                 httpx.Response(200, json=completion())])
        self.assertEqual(result['code'], 0)
        self.assertIn('success=0, repaired=1', result['stdout'])
        self.assertEqual(len(result['reports'][0]['attempts']), 2)

    def test_service_failures_stop_and_count_unprocessed(self):
        """Зупиняє чергу після помилки сервісу, залишаючи вже збережений звіт.

        Перевіряє доступ, баланс, відсутню модель, вичерпаний rate limit та
        збій сервера. Необроблена друга стаття не позначається як failed.
        """
        for status in (401, 402, 403, 404, 408, 429, 503):
            with self.subTest(status=status):
                result = exercise_batch({'A.txt': 'first', 'B.txt': 'second'},
                                        [httpx.Response(status, json={'error': 'test'})])
                self.assertEqual(result['code'], 1)
                self.assertEqual(result['handler'].call_count, 1)
                self.assertEqual(len(result['reports']), 1)
                self.assertIn('не оброблено=1', result['stdout'])

    def test_document_specific_bad_request_continues(self):
        """HTTP 400 окремої статті дозволяє обробити наступну.

        Наприклад, занадто довгий документ не повинен приховувати результати
        решти корпусу. Помилка фіксується у власному звіті та загальному коді 1.
        """
        result = exercise_batch({'A.txt': 'first', 'B.txt': 'second'},
                                [httpx.Response(400, json={'error': 'test'}),
                                 httpx.Response(200, json=completion())])
        self.assertEqual(result['code'], 1)
        self.assertEqual(len(result['reports']), 2)
        self.assertIn('не оброблено=0', result['stdout'])

    def test_missing_root_and_directory_as_document(self):
        """Перевіряє зрозумілі локальні помилки неправильного вибору шляху.

        Відсутній каталог для batch і каталог замість одиночної статті
        відхиляються до API, причому другий випадок підказує --all-documents.
        """
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaises(InputFileError):
                prepare_documents(root / 'unused.txt', True, root / 'absent')
            with self.assertRaisesRegex(InputFileError, '--all-documents'):
                prepare_documents(root, False, root)
