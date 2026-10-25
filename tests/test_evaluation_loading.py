"""Перевірка ідентичності конфігурацій, еталонів та безпечної обробки журналів."""

import tempfile
import unittest
from pathlib import Path

from src.evaluation.loading import load_dataset, load_run, preflight_output
from src.evaluation.models import EvaluationError
from tests.evaluation_helpers import extraction, run_data, workspace, write_json


class LoadingTests(unittest.TestCase):
    """Ізолює вхідні помилки: вони не повинні маскуватися низькою або високою якістю."""

    def test_grouping_and_repeated_root(self):
        """Маршрут і sampling утворюють окремі конфігурації; повтор каталогу не додає runs."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            golden, runs, manifest, rules = workspace(root)
            write_json(runs / 'run_two.json', run_data(provider='other-route'))
            write_json(runs / 'run_three.json', run_data(sampling={'temperature': .5, 'top_p': 1}))
            dataset = load_dataset(golden, [runs, runs], manifest, rules)
            self.assertEqual(len(dataset.groups), 3)
            self.assertTrue(any('Повторний' in warning for warning in dataset.warnings))

    def test_config_key_order_and_missing_snapshot(self):
        """Порядок ключів не створює нову групу; unknown snapshot не підміняється requested."""
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder) / 'a.json', Path(folder) / 'b.json'
            one = run_data()
            two = run_data(sampling={'top_p': 1, 'temperature': 0})
            write_json(a, one)
            write_json(b, two)
            self.assertEqual(load_run(a).group_id, load_run(b).group_id)
            two['attempts'][0].pop('returned_model')
            two.pop('limits')
            write_json(b, two)
            self.assertIsNone(load_run(b).config['returned_model'])
            self.assertNotEqual(load_run(a).group_id, load_run(b).group_id)

    def test_duplicate_run_is_fatal(self):
        """Два файли одного ID/конфігурації не повинні непомітно вибирати найкращий результат."""
        with tempfile.TemporaryDirectory() as folder:
            golden, runs, manifest, rules = workspace(Path(folder))
            write_json(runs / 'run_duplicate.json', run_data())
            with self.assertRaisesRegex(EvaluationError, 'Дублікат'):
                load_dataset(golden, [runs], manifest, rules)

    def test_golden_duplicates_and_invalid_expected(self):
        """Некоректний еталон не використовується для звіту, навіть у provisional режимі."""
        with tempfile.TemporaryDirectory() as folder:
            golden, runs, manifest, rules = workspace(Path(folder))
            row = {'document_id': 'D1', 'annotation_status': 'approved', 'expected': extraction()}
            for values in ([row, row], [{**row, 'expected': {}}]):
                write_json(golden, values)
                with self.assertRaises(EvaluationError):
                    load_dataset(golden, [runs], manifest, rules)

    def test_strict_golden_and_unknown_status(self):
        """Лише approved допускає strict; невідомий статус не є затвердженням."""
        with tempfile.TemporaryDirectory() as folder:
            golden, runs, manifest, rules = workspace(Path(folder), 'needs_human_review')
            self.assertTrue(load_dataset(golden, [runs], manifest, rules).provisional)
            with self.assertRaisesRegex(EvaluationError, 'D1:needs_human_review'):
                load_dataset(golden, [runs], manifest, rules, True)

    def test_invalid_result_keeps_envelope_not_raw(self):
        """Невалідний result не відновлюється з коректного raw_content і лишається в coverage."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'run.json'
            data = run_data()
            data['result'].pop('components')
            data['attempts'][0]['raw_content'] = '{}'
            write_json(path, data)
            run = load_run(path)
            self.assertIsNone(run.result)
            self.assertIn('invalid_result', run.problems)

    def test_failed_result_and_first_pass_conflict(self):
        """Конфліктні метадані діагностуються; failed не стає валідним через ненульовий result."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'run.json'
            write_json(path, run_data(status='failed', first_pass_valid=False))
            run = load_run(path)
            self.assertIsNone(run.result)
            self.assertIn('failed_with_result', run.problems)
            self.assertIn('first_pass_conflict', run.problems)

    def test_malformed_json_nan_and_missing_id(self):
        """Нечитабельний JSON/NaN/ID не дозволяє побудувати достовірну конфігурацію."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'run.json'
            for body in ('{broken', '{"x":NaN}', '{}'):
                path.write_text(body, encoding='utf-8')
                with self.assertRaises(EvaluationError):
                    load_run(path)

    def test_output_paths_and_existing_files(self):
        """Оцінювання не перезаписує runs чи файли, які містяться у вибраному output."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            golden, runs, manifest, rules = workspace(root)
            for output in (root, runs, runs / 'reports'):
                with self.assertRaises(EvaluationError):
                    preflight_output(output, [runs], [golden, manifest, rules])
            out = root / 'reports'
            out.mkdir()
            (out / 'user.txt').write_text('keep', encoding='utf-8')
            with self.assertRaises(EvaluationError):
                preflight_output(out, [runs], [golden])


if __name__ == '__main__':
    unittest.main()
