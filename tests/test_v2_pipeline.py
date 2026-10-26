"""Offline single/batch/provenance та failure-сценарії через справжній конвеєр."""

import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

import main
from src.client_factory import create_client
from src.document_runner import prepare_article_text
from src.extraction import extract_document
from src.schemas import SCHEMA_V2
from src.evaluation_v2.runner import evaluate
from tests.helpers import completion, settings
from tests.test_schema_v2 import example


class V2PipelineTests(unittest.TestCase):
    """Перевіряє реальну серіалізацію й маршрутизацію, замінюючи тільки HTTP."""

    def test_demo_30_and_10_with_provenance(self):
        """Mock запускає 30/10 документів та demo з implicit prompt; inputs однакові."""
        sent, seen = [], {}
        def respond(request):
            """Фіксує лише тестові payload, не використовує API або golden labels."""
            sent.append(json.loads(request.content))
            return httpx.Response(200, json=completion(json.dumps(example())))
        with tempfile.TemporaryDirectory() as directory, \
                httpx.Client(transport=httpx.MockTransport(respond)) as http:
            def factory(config, unused_http, **options):
                """Передає production Settings/SchemaSpec транспорту MockTransport."""
                return create_client(config, http, **options)
            for label, options, count in [
                    ('all', ['--all-documents'], 30),
                    ('golden', ['--document-ids', 'data/sourses/hm1/golden_v2_ids.txt'], 10),
                    ('demo', ['--document', 'data/sourses/hm1/texts/uk/HR-0187.txt'], 1)]:
                output = Path(directory) / label
                with patch('main.load_settings', return_value=settings(provider='openai', temperature=.7)), \
                        patch('src.document_runner.create_client', side_effect=factory), \
                        contextlib.redirect_stdout(io.StringIO()):
                    code = main.main(['--schema-version', 'v2', '--temperature', '0', '--top-p', '1',
                                      '--output-dir', str(output), *options])
                self.assertEqual(code, 0)
                files = list(output.glob('run_*.json'))
                self.assertEqual(len(files), count)
                plan = json.loads((output / 'experiment_manifest.json').read_text(encoding='utf-8'))
                self.assertEqual(plan['planned_count'], count)
                for path in files:
                    row = json.loads(path.read_text(encoding='utf-8'))
                    original = Path(row['source_path']).read_bytes()
                    prepared = prepare_article_text(original.decode('utf-8'))
                    self.assertEqual(row['source_sha256'], hashlib.sha256(original).hexdigest())
                    self.assertEqual(row['input_text_sha256'], hashlib.sha256(prepared.encode()).hexdigest())
                    self.assertEqual(row['schema_sha256'], SCHEMA_V2.sha256)
                    self.assertEqual(row['sampling'], {'temperature': 0, 'top_p': 1})
                    self.assertEqual(row['prompt']['namespace'], 'schema_v2')
                    previous = seen.setdefault(row['document_id'], row['input_text_sha256'])
                    self.assertEqual(previous, row['input_text_sha256'])
                if label == 'golden':
                    result, code = evaluate(Path('data/sourses/hm1/golden_v2.json'), [output],
                                            Path(directory) / 'evaluation',
                                            Path('data/sourses/hm1/manifest.json'),
                                            Path('data/golden_annotation_rules_v2.md'))
                    self.assertEqual(code, 0)
                    group = result['groups'][0]
                    self.assertEqual(group['quality']['aggregate_accuracy']['denominator'], 80)
                    self.assertEqual(group['quality']['content_accuracy']['denominator'], 70)
                    self.assertEqual(group['coverage']['received_golden'], 10)
        self.assertEqual(len(sent), 41)
        # User text — саме prepared TXT; жодного title/language/topic з manifest.
        user_texts = {payload['messages'][1]['content'] for payload in sent}
        for path in main.TEXTS_ROOT.rglob('*.txt'):
            text = prepare_article_text(path.read_bytes().decode('utf-8'))
            self.assertIn(text, user_texts)

    def test_invalid_cli_never_calls_pipeline(self):
        """Unknown schema, взаємовиключний вибір і invalid top_p не викликають HTTP."""
        for args in [['--schema-version', 'v3'], ['--document', 'x', '--all-documents']]:
            with patch('main.run_documents') as run, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    main.main(args)
                run.assert_not_called()
        for value in ['0', '-0.1', '1.1', 'nan', 'inf']:
            with patch('main.load_settings', return_value=settings()), patch('main.run_documents') as run, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main.main(['--top-p', value]), 2)
                run.assert_not_called()

    def test_refusal_truncation_and_second_invalid(self):
        """Правильна форма не маскує refusal/truncation; два invalid завершуються failed."""
        refusal = completion(json.dumps(example()))
        refusal['choices'][0]['message']['refusal'] = 'synthetic refusal'
        for response in [refusal, completion(json.dumps(example()), finish_reason='length'), completion('{}')]:
            calls = []
            def respond(request):
                """Повертає заданий збій щоразу, щоб перевірити межі repair."""
                calls.append(request)
                return httpx.Response(200, json=response)
            with httpx.Client(transport=httpx.MockTransport(respond)) as http:
                result = extract_document(create_client(settings(), http, schema_spec=SCHEMA_V2), 'extract', 'article')
            self.assertEqual(result['status'], 'failed')
            self.assertIsNone(result['result'])
            self.assertLessEqual(len(calls), 2)

    def test_v2_retry_is_not_repair(self):
        """HTTP 500 + valid response дають дві HTTP спроби, але одну генерацію."""
        responses = iter([httpx.Response(500, json={'error': 'synthetic'}),
                          httpx.Response(200, json=completion(json.dumps(example())))])
        with httpx.Client(transport=httpx.MockTransport(lambda request: next(responses))) as http:
            client = create_client(settings(), http, schema_spec=SCHEMA_V2)
            client.sleep = lambda seconds: None
            result = extract_document(client, 'extract', 'synthetic article')
        self.assertEqual(result['status'], 'success')
        self.assertTrue(result['first_pass_valid'])
        self.assertEqual(len(result['attempts']), 1)
        self.assertEqual(len(result['attempts'][0]['requests']), 2)
