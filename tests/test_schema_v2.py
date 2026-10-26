"""Офлайнова перевірка контракту, API payload та незалежних метрик v2."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from pydantic import ValidationError

import main
from src.client_factory import create_client
from src.document_runner import prepare_article_text, select_document_ids, InputFileError
from src.extraction import extract_document
from src.schemas import SCHEMA_V1, SCHEMA_V2, get_schema
from src.evaluation_v2.scoring import score, aggregate
from tests.helpers import completion, settings


def example() -> dict:
    """Створює штучний v2 об’єкт, незалежний від golden і реальних відповідей."""
    return dict(language='uk', primary_topic='devices_automation', mentioned_platforms=[],
                mentioned_interfaces=[], mentions_sensor=False, mentions_display=False,
                mentions_battery=False, mentions_motor=False)


class SchemaV2Tests(unittest.TestCase):
    """Відрізняє суворі типи, допустимий порядок тегів і справжню помилку даних."""

    def test_invalid_values(self):
        """Null, bool coercion, unknown enum та дублікати не стають валідним JSON."""
        for field, value in [('language', 'de'), ('mentions_sensor', 0), ('mentions_sensor', 1),
                             ('mentions_sensor', 'false'), ('mentioned_platforms', None),
                             ('mentioned_platforms', ['arduino', 'arduino']),
                             ('mentioned_interfaces', ['invalid'])]:
            with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                SCHEMA_V2.model.model_validate({**example(), field: value})
        for row in [{**example(), 'extra': 1}, {k: v for k, v in example().items() if k != 'language'}]:
            with self.assertRaises(ValidationError):
                SCHEMA_V2.model.model_validate(row)

    def test_canonical_order_preserves_input(self):
        """Перестановка приймається без repair; вхідний словник не змінюється."""
        row = {**example(), 'mentioned_platforms': ['esp32', 'arduino']}
        original = copy.deepcopy(row)
        self.assertEqual(SCHEMA_V2.model.model_validate(row).mentioned_platforms, ['arduino', 'esp32'])
        self.assertEqual(row, original)
        self.assertIs(get_schema(), SCHEMA_V1)
        with self.assertRaises(ValueError):
            get_schema('v3')

    def test_provider_schema_matrix(self):
        """Усі три маршрути надсилають обраний контракт і точні sampling overrides."""
        for provider in ('openai', 'openrouter', 'ollama'):
            for schema in (SCHEMA_V1, SCHEMA_V2):
                with self.subTest(provider=provider, schema=schema.version):
                    sent = []
                    def respond(request):
                        """Зберігає реальне тіло mock HTTP-запиту для assertions."""
                        sent.append(json.loads(request.content))
                        return httpx.Response(200, json=completion(json.dumps(example())))
                    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
                        client = create_client(settings(provider=provider, temperature=0, top_p=1),
                                               http, schema_spec=schema)
                        client.complete([{'role': 'user', 'content': 'synthetic text'}])
                    self.assertEqual(sent[0]['response_format']['json_schema']['schema'], schema.api_schema)
                    self.assertEqual((sent[0]['temperature'], sent[0]['top_p']), (0, 1))
                    self.assertNotIn('offline-test-key', json.dumps(sent[0]))

    def test_duplicate_repaired_once(self):
        """Невалідні дублікати викликають рівно одну repair-генерацію зі збереженим raw."""
        bad = {**example(), 'mentioned_platforms': ['arduino', 'arduino']}
        responses = iter([completion(json.dumps(bad)), completion(json.dumps(example()))])
        with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=next(responses)))) as http:
            client = create_client(settings(), http, schema_spec=SCHEMA_V2)
            result = extract_document(client, 'extract', 'synthetic article')
        self.assertEqual(result['status'], 'repaired')
        self.assertFalse(result['first_pass_valid'])
        self.assertEqual(len(result['attempts']), 2)
        self.assertEqual(json.loads(result['attempts'][0]['raw_content']), bad)

    def test_v1_v2_are_not_interchangeable(self):
        """Кожна модель відхиляє об’єкт іншої версії, навіть якщо він валідний там."""
        from tests.helpers import valid_result
        for model, value in [(SCHEMA_V1.model, example()), (SCHEMA_V2.model, valid_result())]:
            with self.assertRaises(ValidationError):
                model.model_validate(value)


class PreparationTests(unittest.TestCase):
    """Підготовка видаляє тільки відомий header, залишаючи зміст і код."""

    def test_header_and_counterexamples(self):
        """Зіставляє exact prepared bytes і контрприклади без широкого regex."""
        body = '\n\nКод:\n```\nАвтори: user\nКатегорії: sensor\nПлати: Arduino\n```\n'
        text = 'Назва\nАвтори: A\nКатегорії: B\nПлати: C\n' + body
        actual = prepare_article_text(text)
        self.assertEqual(actual, 'Назва\n' + body)
        self.assertEqual(prepare_article_text(actual), actual)
        for text in ['Назва\nАвтори: A\nТекст статті',
                     'Назва\n> Автори: A\n> Категорії: B\n> Плати: C',
                     'Назва\nАбзац про Автори: A\nКатегорії: B\nПлати: C']:
            self.assertEqual(prepare_article_text(text), text)

    def test_ids_selection(self):
        """Unknown/duplicate/empty ID відхиляються до мережі."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'HR-0001.txt').write_text('article', encoding='utf-8')
            ids = root / 'ids'
            ids.write_text('HR-0001', encoding='utf-8')
            self.assertEqual(len(select_document_ids(ids, root)), 1)
            for text in ['', 'HR-0002', 'HR-0001\nHR-0001']:
                ids.write_text(text, encoding='utf-8')
                with self.assertRaises(InputFileError):
                    select_document_ids(ids, root)

    def test_cli_defaults_and_zero_override(self):
        """V2 demo обирає свій prompt; CLI zero перекриває config 0.7."""
        args = main.parse_args(['--schema-version', 'v2'])
        self.assertEqual(args.prompt.parts[-3:], ('prompts', 'schema_v2', 'v1.txt'))
        with tempfile.TemporaryDirectory() as directory, patch('main.load_settings', return_value=settings(temperature=.7)), \
                patch('main.run_documents') as run:
            run.return_value.failed = 0
            run.return_value.not_processed = 0
            self.assertEqual(main.main(['--schema-version', 'v2', '--temperature', '0',
                                        '--output-dir', directory]), 0)
            self.assertEqual(run.call_args.args[0].temperature, 0)
        for value in ['nan', 'inf', '-1', '3']:
            with patch('main.load_settings', return_value=settings()), patch('main.run_documents') as run:
                self.assertEqual(main.main(['--temperature', value]), 2)
                run.assert_not_called()


class ExactMetricsTests(unittest.TestCase):
    """Контролює ручну арифметику і знаменники при пропущених документах."""

    def test_missing_and_language(self):
        """G=2: correct+missing → 8/16 і 7/14; мова не додається до content."""
        gold = example()
        docs = [{'fields': score(gold, gold)}, {'fields': score(gold, None)}]
        result = aggregate(docs)
        self.assertEqual(result['aggregate_accuracy']['value'], .5)
        self.assertEqual(result['content_accuracy']['denominator'], 14)
        wrong = {**gold, 'primary_topic': 'power_batteries', 'mentioned_platforms': ['arduino'],
                 'mentioned_interfaces': ['usb'], 'mentions_sensor': True, 'mentions_display': True,
                 'mentions_battery': True, 'mentions_motor': True}
        result = aggregate([docs[0], {'fields': score(gold, wrong)}])
        self.assertEqual(result['aggregate_accuracy']['numerator'], 9)
        self.assertEqual(result['content_accuracy']['numerator'], 7)

    def test_set_precision_recall(self):
        """Перетин із двох тегів дає TP=FP=FN=1, P=R=F1=0.5."""
        gold = {**example(), 'mentioned_platforms': ['arduino', 'esp32']}
        pred = {**example(), 'mentioned_platforms': ['arduino', 'stm32']}
        metrics = aggregate([{'fields': score(gold, pred)}])['lists']['mentioned_platforms']
        self.assertEqual([metrics[k] for k in ('tp', 'fp', 'fn')], [1, 1, 1])
        self.assertEqual([metrics[k]['value'] for k in ('precision', 'recall', 'f1')], [.5, .5, .5])
