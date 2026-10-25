"""Незалежно розраховані приклади для знаменників, usage, repair і цін."""

import copy
import tempfile
import unittest
from pathlib import Path

from src.evaluation.loading import load_run
from src.evaluation.metrics import aggregate_quality, percentile, prf, runtime_metrics
from src.evaluation.models import EvaluationError
from src.evaluation.scoring import score_document
from src.evaluation.usage import load_pricing, usage_metrics
from tests.evaluation_helpers import component, extraction, run_data, write_json


class MetricTests(unittest.TestCase):
    """Порівнює обчислення з відомою вручну арифметикою, включно з unknown."""

    def make_run(self, root: Path, data: dict):
        """Записує одну фікстуру та читає тим самим loader, що використовує CLI."""
        path = root / 'run_test.json'
        write_json(path, data)
        return load_run(path)

    def test_prf_and_empty_sets(self):
        """TP=2 FP=1 FN=3 дає P=2/3 R=2/5 F1=1/2; порожнє є undefined."""
        actual = prf(dict(tp=2, fp=1, fn=3), 'fixture')
        self.assertAlmostEqual(actual['precision']['value'], 2 / 3)
        self.assertEqual(actual['recall']['value'], .4)
        self.assertEqual(actual['f1']['value'], .5)
        self.assertIsNone(prf(dict(tp=0, fp=0, fn=0), '')['f1']['value'])
        self.assertEqual(prf(dict(tp=0, fp=0, fn=1), '')['f1']['value'], 0)

    def test_missing_doc_in_exact_denominator(self):
        """Один повний і один відсутній прогноз дають exact aggregate=8/16, не 8/8."""
        gold = extraction(components=[component()])
        documents = [{'fields': score_document(gold, gold)}, {'fields': score_document(gold, None)}]
        metrics = aggregate_quality(documents)
        self.assertEqual(metrics['aggregate_exact_accuracy']['value'], .5)
        self.assertEqual(metrics['aggregate_exact_accuracy']['denominator'], 16)
        self.assertEqual(metrics['lists']['components']['identity']['fn'], 1)
        review = metrics['review']
        self.assertEqual(sum(review['check_counts'].values()), review['total_checks'])
        self.assertEqual(review['unavailable_checks'], 8)

    def test_percentiles_small_samples(self):
        """Один вимір дає себе; p95 двох значень інтерполюється, порожній список — None."""
        self.assertIsNone(percentile([], .95))
        self.assertEqual(percentile([8], .95), 8)
        self.assertEqual(percentile([0, 10], .95), 9.5)

    def test_usage_does_not_duplicate_copies(self):
        """Один HTTP usage, повторений у envelope, враховується тільки один раз."""
        with tempfile.TemporaryDirectory() as folder:
            run = self.make_run(Path(folder), run_data())
            metrics = usage_metrics([run], [])
        self.assertEqual(metrics['prompt_tokens']['known_sum'], 10)
        self.assertEqual(metrics['completion_tokens']['mean_per_complete_document'], 5)
        self.assertIsNone(metrics['cost']['partial_known_cost'])
        self.assertIsNone(metrics['cost']['cost_per_1000_documents'])

    def test_retry_missing_usage_makes_document_incomplete(self):
        """Невідомий usage невдалого retry не перетворюється на нульовий тариф."""
        data = run_data()
        data['attempts'][0]['requests'].insert(0, {'response': None})
        with tempfile.TemporaryDirectory() as folder:
            run = self.make_run(Path(folder), data)
            metrics = usage_metrics([run], [])
        self.assertEqual(metrics['prompt_tokens']['known_sum'], 10)
        self.assertEqual(metrics['prompt_tokens']['unknown_requests'], 1)
        self.assertEqual(metrics['prompt_tokens']['complete_documents'], 0)
        self.assertIsNone(metrics['prompt_tokens']['mean_per_complete_document'])

    def test_repair_counts_both_generations(self):
        """Repair додає usage обох генерацій, але не робить первинну відповідь валідною."""
        data = run_data(status='repaired', first_pass_valid=False)
        data['attempts'].append(copy.deepcopy(data['attempts'][0]))
        data['attempts'][0]['result'] = None
        with tempfile.TemporaryDirectory() as folder:
            run = self.make_run(Path(folder), data)
            metrics = runtime_metrics([run], [])
        self.assertEqual(metrics['valid_final']['value'], 1)
        self.assertEqual(metrics['valid_first_confirmed']['value'], 0)
        self.assertEqual(metrics['usage']['prompt_tokens']['known_sum'], 20)

    def test_unknown_latency_and_first_pass(self):
        """Відсутні runtime дані не стають нульовою latency або відомим first-pass false."""
        data = run_data(latency_seconds=None)
        data['attempts'][0].pop('result')
        with tempfile.TemporaryDirectory() as folder:
            metrics = runtime_metrics([self.make_run(Path(folder), data)], [])
        self.assertIsNone(metrics['latency']['p50'])
        self.assertEqual(metrics['unknown_first_attempts'], 1)
        self.assertIsNone(metrics['valid_first_known']['value'])
        self.assertEqual(metrics['latency']['cold_start'], 'unknown_not_separated')

    def test_tariff_and_api_priority(self):
        """Знижка кешу обчислюється явно; фактичний API cost має пріоритет над тарифом."""
        data = run_data()
        usage = data['attempts'][0]['requests'][0]['response']['usage']
        usage['prompt_tokens_details']['cached_tokens'] = 4
        pricing = [{'provider': 'test', 'requested_model': 'test-model', 'returned_model': 'test-model-v1',
                    'input_per_million': 2, 'cached_input_per_million': 1, 'output_per_million': 4}]
        with tempfile.TemporaryDirectory() as folder:
            run = self.make_run(Path(folder), data)
            self.assertAlmostEqual(usage_metrics([run], pricing)['cost']['partial_known_cost'], .000036)
            usage['cost'] = .25
            run = self.make_run(Path(folder), data)
            self.assertEqual(usage_metrics([run], pricing)['cost']['cost_per_1000_documents'], 250)

    def test_partial_cost_not_full_extrapolation(self):
        """Відома ціна одного з двох запитів не видається за повну ціну документа."""
        data = run_data()
        data['attempts'][0]['requests'][0]['response']['usage']['cost'] = .01
        data['attempts'][0]['requests'].insert(0, {'response': None})
        with tempfile.TemporaryDirectory() as folder:
            metrics = usage_metrics([self.make_run(Path(folder), data)], [])['cost']
        self.assertEqual(metrics['partial_known_cost'], .01)
        self.assertEqual(metrics['priced_requests'], 1)
        self.assertIsNone(metrics['cost_per_1000_documents'])

    def test_pricing_validation(self):
        """Ціни без дати/джерела або з некоректними числами не приймаються."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'pricing.json'
            write_json(path, [{'input_per_million': 1}])
            with self.assertRaises(EvaluationError):
                load_pricing(path)
            row = {'provider': 'test', 'requested_model': 'test-model', 'returned_model': 'test-model-v1',
                   'as_of': '2026-10-25', 'source_url': 'https://example.org/pricing', 'currency': 'USD',
                   'input_per_million': 1, 'output_per_million': 2}
            write_json(path, [row])
            self.assertEqual(len(load_pricing(path)), 1)
            write_json(path, [row, row])
            with self.assertRaises(EvaluationError):
                load_pricing(path)


if __name__ == '__main__':
    unittest.main()
