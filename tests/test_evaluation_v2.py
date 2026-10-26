"""Інтеграційні offline fixtures v2 без мережі, .env або semantic scorer."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.evaluation.models import EvaluationError
from src.evaluation_v2.runner import evaluate
from src.evaluation_v2.loading import load_run
from src.schemas import SCHEMA_V2
from tests.test_schema_v2 import example


class EvaluationV2Tests(unittest.TestCase):
    """Перевіряє цілий цикл читання, coverage, метрик і захищеного запису."""

    def setUp(self):
        """Створює два штучні еталони й один run; це не експериментальні дані."""
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runs = self.root / 'runs'
        self.runs.mkdir()
        self.plan = dict(schema_version='v2', experiment_id='synthetic', provider='openai', model='test/model',
                         planned_ids=['X', 'Y'], planned_count=2, schema_sha256=SCHEMA_V2.sha256,
                         prompt_namespace='schema_v2', prompt_version='v1', prompt_sha256='a' * 64,
                         sampling={'temperature': 0, 'top_p': 1})
        self.row = dict(schema_version='v2', schema_sha256=SCHEMA_V2.sha256, document_id='X',
                        provider='openai', requested_model='test/model', experiment_id='synthetic',
                        source_sha256='b' * 64, input_text_sha256='c' * 64,
                        text_preparation_version='schema-v2-text-v1', kind='primary',
                        prompt={'namespace': 'schema_v2', 'version': 'v1', 'sha256': 'a' * 64},
                        sampling=self.plan['sampling'], status='success', first_pass_valid=True,
                        result=example(), attempts=[{'result': example()}], latency_seconds=2)
        self.write(self.runs / 'run_x.json', self.row)
        self.write(self.runs / 'experiment_manifest.json', self.plan)
        self.golden = self.root / 'golden.json'
        self.write(self.golden, [dict(schema_version='v2', document_id=doc, expected=example(),
                                      annotation_status='needs_human_review') for doc in ['X', 'Y']])
        self.manifest = self.root / 'manifest.json'
        self.write(self.manifest, [{'id': 'X'}, {'id': 'Y'}])
        self.rules = self.root / 'rules.md'
        self.rules.write_text('synthetic rules', encoding='utf-8')

    def write(self, path, value):
        """Серіалізує тільки тимчасові тестові дані у UTF-8 JSON."""
        path.write_text(json.dumps(value), encoding='utf-8')

    def run_evaluation(self, **kwargs):
        """Викликає evaluator на fixture; читання .env та HTTP заборонене mocks."""
        with patch('socket.socket', side_effect=AssertionError('network forbidden')), \
                patch('dotenv.load_dotenv', side_effect=AssertionError('.env forbidden')):
            return evaluate(self.golden, [self.runs], self.root / 'out', self.manifest, self.rules, **kwargs)

    def test_end_to_end_missing_and_unknown_cost(self):
        """Один missing дає partial і 8/16; вартість без usage не вигадується."""
        summary, code = self.run_evaluation()
        self.assertEqual(code, 1)
        self.assertEqual(summary['annotation_status'], 'provisional')
        group = summary['groups'][0]
        self.assertEqual(group['quality']['aggregate_accuracy']['numerator'], 8)
        self.assertEqual(group['quality']['aggregate_accuracy']['denominator'], 16)
        self.assertEqual(group['runtime']['valid_over_golden']['value'], .5)
        self.assertEqual(group['coverage']['missing_primary_ids'], ['Y'])
        self.assertEqual(group['runtime']['latency']['sample_count'], 1)
        self.assertTrue((self.root / 'out/summary.json').is_file())
        with self.assertRaises(EvaluationError):
            self.run_evaluation()

    def test_strict_and_duplicate_rejected(self):
        """Human approval не підміняється валідністю JSON; duplicate не вибирає кращий run."""
        with self.assertRaises(EvaluationError):
            self.run_evaluation(strict=True)
        self.write(self.runs / 'run_duplicate.json', self.row)
        with self.assertRaises(EvaluationError):
            self.run_evaluation()
        self.assertFalse((self.root / 'out/summary.json').exists())

    def test_schema_and_sampling_rejected(self):
        """Стороння схема, probe і invalid sampling не потрапляють у primary metrics."""
        for field, value in [('schema_version', 'v1'), ('schema_sha256', 'unknown'),
                             ('kind', 'probe'), ('sampling', {'temperature': -1, 'top_p': 1})]:
            self.write(self.runs / 'run_x.json', {**self.row, field: value})
            with self.subTest(field=field), self.assertRaises(EvaluationError):
                load_run(self.runs / 'run_x.json', self.plan)

    def test_failed_with_valid_shape_is_failed(self):
        """Failed статус не стає success через структурно правильний result."""
        self.write(self.runs / 'run_x.json', {**self.row, 'status': 'failed'})
        run = load_run(self.runs / 'run_x.json', self.plan)
        self.assertIsNone(run.result)

    def test_deterministic_replay(self):
        """Другий output з тими самими inputs має тотожні метрики й provenance."""
        first, _ = self.run_evaluation()
        second, _ = evaluate(self.golden, [self.runs], self.root / 'other', self.manifest, self.rules)
        self.assertEqual(first, second)

    def test_transport_failure_keeps_group(self):
        """Failed без returned_model лишається у групі з успішним запитом моделі."""
        self.row['attempts'][0]['returned_model'] = 'test/snapshot'
        self.write(self.runs / 'run_x.json', self.row)
        failed = {**self.row, 'document_id': 'Y', 'status': 'failed', 'result': None,
                  'first_pass_valid': False, 'attempts': [{'result': None}]}
        self.write(self.runs / 'run_y.json', failed)
        summary, code = self.run_evaluation()
        self.assertEqual(code, 0)
        self.assertEqual(len(summary['groups']), 1)
        self.assertEqual(summary['groups'][0]['runtime']['valid_over_golden']['value'], .5)

    def test_malformed_and_mixed_schema(self):
        """Пошкоджений JSON і чужий envelope дають діагностику до запису summary."""
        path = self.runs / 'run_x.json'
        for content in ['{', json.dumps({**self.row, 'schema_version': 'v1'})]:
            path.write_text(content, encoding='utf-8')
            with self.assertRaises(EvaluationError):
                self.run_evaluation()

    def test_output_write_failure(self):
        """Помилка запису не видається за успішний готовий звіт."""
        with patch('src.evaluation_v2.runner.write_reports', side_effect=OSError('synthetic write failure')):
            with self.assertRaises(OSError):
                self.run_evaluation()
        self.assertFalse((self.root / 'out/summary.json').exists())
