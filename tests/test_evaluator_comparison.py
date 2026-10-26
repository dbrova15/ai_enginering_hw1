"""Перевірка відтворюваності звіту до/після та незмінності бази порівняння."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from src.evaluation.comparison import compare
from src.evaluation.models import EvaluationError
from src.evaluation.runner import evaluate
from tests.evaluation_helpers import workspace, write_json
from tests.semantic_controls import run_controls


class EvaluatorComparisonTests(unittest.TestCase):
    """Не дозволяє приписувати evaluator зміну вхідних даних або підмінених контролів."""

    def prepare(self, root: Path) -> tuple:
        """Створює два порівнювані звіти та однакові контрольні факти у temp-папці."""
        golden, runs, manifest, rules = workspace(root)
        before, after = root / 'before', root / 'after'
        for output in (before, after):
            evaluate(golden, [runs], output, manifest, rules)
        old_controls, new_controls = root / 'old.json', root / 'new.json'
        result = run_controls()
        write_json(old_controls, result)
        write_json(new_controls, result)
        return before, after, old_controls, new_controls, root / 'comparison'

    def test_same_inputs_and_measured_fn_fix(self):
        """Рахунок FN-fixed спирається на verdict фактичних іменованих контролів, а не загальний F1."""
        with tempfile.TemporaryDirectory() as folder:
            args = self.prepare(Path(folder))
            before = json.loads(args[2].read_text(encoding='utf-8'))
            positive = next(c for c in before['cases'] if c['verdict'] == 'match')
            positive['actual'] = 'missing'
            write_json(args[2], before)
            result = compare(*args)
            self.assertEqual(result['controls']['fixed_fn_ids'], [positive['id']])
            self.assertTrue((args[-1] / 'before_after.md').exists())

    def test_changed_input_fingerprints_rejected(self):
        """Зміна вхідного snapshot блокує порівняння як нібито виключно зміну evaluator."""
        with tempfile.TemporaryDirectory() as folder:
            args = self.prepare(Path(folder))
            path = args[1] / 'summary.json'
            data = json.loads(path.read_text(encoding='utf-8'))
            data['provenance']['inputs']['changed_input'] = 'bad'
            write_json(path, data)
            with self.assertRaises(EvaluationError):
                compare(*args)
            self.assertFalse(args[-1].exists())

    def test_mutated_controls_rejected(self):
        """Не можна поліпшити результат, змінивши контрольний факт між вимірами."""
        with tempfile.TemporaryDirectory() as folder:
            args = self.prepare(Path(folder))
            data = json.loads(args[3].read_text(encoding='utf-8'))
            data['cases'][0]['predicted']['value'] = '999'
            write_json(args[3], data)
            with self.assertRaises(EvaluationError):
                compare(*args)

    def test_new_false_positive_reported_not_hidden(self):
        """Якщо негативний контроль став match, звіт явно рахує новий false positive."""
        with tempfile.TemporaryDirectory() as folder:
            args = self.prepare(Path(folder))
            data = json.loads(args[3].read_text(encoding='utf-8'))
            negative = next(c for c in data['cases'] if c['verdict'] != 'match')
            negative['actual'] = 'match'
            write_json(args[3], data)
            result = compare(*args)
            self.assertEqual(result['controls']['new_fp_ids'], [negative['id']])
            self.assertEqual(result['controls']['after_fp'], 1)

    def test_comparison_does_not_overwrite(self):
        """Існуючий до/після звіт не перезаписується мовчки повторним запуском."""
        with tempfile.TemporaryDirectory() as folder:
            args = self.prepare(Path(folder))
            compare(*args)
            before = (args[-1] / 'before_after.json').read_bytes()
            with self.assertRaises(EvaluationError):
                compare(*args)
            self.assertEqual((args[-1] / 'before_after.json').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
