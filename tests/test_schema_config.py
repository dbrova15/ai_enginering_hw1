"""Перевірка контракту й налаштувань до будь-якого API-запиту."""

import ast
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from src.config import PROJECT_ROOT, ConfigError, load_settings
from src.schema import ExtractionResult
from tests.helpers import valid_result


class SchemaTests(unittest.TestCase):
    """Перевіряє, що локальна валідація та схема для API мають один контракт.

    Працює з локальними словниками й наявними чернетками golden set; мережу,
    секрети та початкові статті не використовує й не змінює.
    """

    def test_required_nullable_and_nested_schema(self):
        """Перевіряє всі required-ключі, явний null та заборону додаткових полів.

        Вимоги перевіряються і в корені, і у вкладених структурах, щоб API
        отримував повний strict-контракт без прихованих необов'язкових ключів.
        """
        schema = ExtractionResult.model_json_schema()
        for part in [schema, *schema['$defs'].values()]:
            self.assertFalse(part['additionalProperties'])
            self.assertEqual(set(part['required']), set(part['properties']))
        self.assertEqual(ExtractionResult.model_validate(valid_result()).components, [])

    def test_invalid_values_are_rejected(self):
        """Підставляє неправильні категорії, типи та зайві ключі.

        Кожен пошкоджений об'єкт має спричинити ValidationError; автоматичне
        перетворення числа на текст або null на порожній список неприпустиме.
        """
        for field, value in [('document_type', 'wrong'), ('primary_topic', 'wrong'),
                             ('main_subject', 123), ('components', None), ('extra', 'wrong')]:
            with self.subTest(field=field):
                data = {**valid_result(), field: value}
                with self.assertRaises(ValidationError):
                    ExtractionResult.model_validate(data)

    def test_nested_keys_and_types_are_checked(self):
        """Перевіряє тип значення параметра та обов'язковість nullable-ключів.

        Числове value має бути рядком. Відсутній model у компоненті не
        прирівнюється до явно заданого null, потрібного strict-схемі.
        """
        data = valid_result()
        data['technical_parameters'] = [{'subject': None, 'name': 'Напруга', 'value': 5, 'unit': 'V'}]
        with self.assertRaises(ValidationError):
            ExtractionResult.model_validate(data)
        data = valid_result()
        data['components'] = [{'name': 'ADC', 'manufacturer': None, 'role': None}]
        with self.assertRaises(ValidationError):
            ExtractionResult.model_validate(data)

    def test_all_golden_drafts_match_structure(self):
        """Звіряє структуру наявних десяти expected із виконуваною схемою.

        Це не підтверджує правильності фактів і не змінює needs_human_review;
        гарантується лише сумісність форми даних із валідатором.
        """
        rows = json.loads((PROJECT_ROOT / 'data/sourses/hm1/golden.json').read_text(encoding='utf-8'))
        self.assertEqual(len(rows), 10)
        for row in rows:
            with self.subTest(document_id=row['document_id']):
                ExtractionResult.model_validate(row['expected'])


class ConfigTests(unittest.TestCase):
    """Читає тільки тимчасові .env з вигаданими значеннями.

    Оточення процесу ізолюється в кожному тесті, щоб приватний ключ користувача
    не впливав на результат і ніколи не потрапляв у тестовий вивід.
    """

    def test_env_file_and_process_precedence(self):
        """Перевіряє читання .env і пріоритет model ID зі змінної процесу.

        Тимчасовий файл містить тестові значення. Після тесту файл видаляється,
        а справжнє оточення відновлюється контекстним менеджером mock.
        """
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '.env'
            path.write_text('OPENROUTER_API_KEY=test-key\nOPENROUTER_MODEL=file/model\n', encoding='utf-8')
            with patch.dict(os.environ, {'OPENROUTER_MODEL': 'process/model'}, clear=True):
                loaded = load_settings(path)
            self.assertEqual(loaded.model, 'process/model')
            self.assertEqual(loaded.api_key.get_secret_value(), 'test-key')
            self.assertNotIn('test-key', repr(loaded))

    def test_missing_credentials_and_placeholder(self):
        """Відхиляє порожню конфігурацію, ключ-заглушку та ключ замість моделі.

        Усі помилки мають виникнути локально, до мережі, та не показувати
        тестове секретне значення в тексті повідомлення.
        """
        cases = [{}, {'OPENROUTER_API_KEY': 'test-key'},
                 {'OPENROUTER_API_KEY': 'sk-or-...', 'OPENROUTER_MODEL': 'test/model'},
                 {'OPENROUTER_API_KEY': 'test-key', 'OPENROUTER_MODEL': 'sk-or-private'}]
        with tempfile.TemporaryDirectory() as folder:
            for env in cases:
                with self.subTest(keys=list(env)), patch.dict(os.environ, env, clear=True):
                    with self.assertRaises(ConfigError) as error:
                        load_settings(Path(folder) / 'absent.env')
                    self.assertNotIn('sk-or-private', str(error.exception))

    def test_invalid_numeric_settings_hide_secret(self):
        """Перевіряє межі sampling, retry і timeout та відхилення NaN.

        Очікує ConfigError з поясненням порушення, але без ключа. Файл .env
        відсутній, усі дані надходять з ізольованого тестового оточення.
        """
        with tempfile.TemporaryDirectory() as folder:
            for name, value in [('TOP_P', '2'), ('MAX_RETRIES', '-1'),
                                ('TEMPERATURE', 'nan'), ('REQUEST_TIMEOUT_SECONDS', '0')]:
                env = {'OPENROUTER_API_KEY': 'private-test-key', 'OPENROUTER_MODEL': 'test/model', name: value}
                with self.subTest(name=name), patch.dict(os.environ, env, clear=True):
                    with self.assertRaises(ConfigError) as error:
                        load_settings(Path(folder) / 'absent.env')
                    self.assertNotIn('private-test-key', str(error.exception))


class DocumentationTests(unittest.TestCase):
    """Контролює окрему вимогу користувача про пояснення всіх класів і функцій.

    Аналізує вихідний код без його запуску. Так перевірка не залежить від
    сторонніх класів бібліотек або автоматично створених Pydantic-методів.
    """

    def test_all_own_classes_and_functions_have_docstrings(self):
        """Шукає власні класи й функції без docstring у main, src і tests.

        Порожній або відсутній опис спричиняє помилку з файлом і номером рядка.
        Зміст пояснень додатково переглядається під час рев'ю коду.
        """
        paths = [PROJECT_ROOT / 'main.py', *sorted((PROJECT_ROOT / 'src').glob('*.py')),
                 *sorted((PROJECT_ROOT / 'tests').glob('*.py'))]
        for path in paths:
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    with self.subTest(path=path.name, line=node.lineno, name=node.name):
                        self.assertTrue(ast.get_docstring(node))
