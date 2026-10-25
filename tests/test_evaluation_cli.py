"""Повні офлайнові сценарії CLI: звіти, діагностика, детермінізм і незмінність."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluate import main
from src.evaluation.models import digest
from tests.evaluation_helpers import extraction, run_data, workspace, write_json


class CliTests(unittest.TestCase):
    """Перевіряє користувацькі сценарії в ізольованих каталогах без мережі й ключів."""

    def invoke(self, paths: tuple, output: Path, extra: list | None = None) -> int:
        """Викликає CLI з тестовими шляхами, перехоплюючи службовий stdout/stderr."""
        golden, runs, manifest, rules = paths
        argv = ['--golden', str(golden), '--runs', str(runs), '--output-dir', str(output),
                '--manifest', str(manifest), '--annotation-rules', str(rules), *(extra or [])]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return main(argv)

    def test_complete_run_writes_three_reports_and_preserves_inputs(self):
        """Повний approved прогін створює звіти й залишає всі байти входів незмінними."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths = workspace(root)
            hashes = {p: digest(p) for p in root.rglob('*') if p.is_file()}
            out = root / 'output'
            with patch('socket.create_connection', side_effect=AssertionError('network forbidden')):
                self.assertEqual(self.invoke(paths, out), 0)
            self.assertEqual({p.name for p in out.iterdir()}, {'summary.json', 'details.json', 'comparison.md'})
            summary = json.loads((out / 'summary.json').read_text(encoding='utf-8'))
            self.assertEqual(summary['groups'][0]['quality']['aggregate_exact_accuracy']['value'], 1)
            self.assertEqual(summary['evaluation_status'], 'approved_labels')
            self.assertEqual(hashes, {p: digest(p) for p in hashes})

    def test_provisional_and_strict_no_output(self):
        """Provisional дозволено, але strict не створює навіть каталог фінальних результатів."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths = workspace(root, 'needs_human_review')
            self.assertEqual(self.invoke(paths, root / 'provisional'), 0)
            report = (root / 'provisional/comparison.md').read_text(encoding='utf-8')
            self.assertIn('Evaluation status: provisional (golden labels not fully approved)', report)
            self.assertEqual(self.invoke(paths, root / 'strict', ['--strict-golden']), 2)
            self.assertFalse((root / 'strict').exists())

    def test_missing_document_keeps_denominator(self):
        """Неповний coverage дає exit 1 і не зменшує знаменник quality до наявних документів."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths = workspace(root)
            write_json(paths[0], [{'document_id': doc, 'annotation_status': 'approved', 'expected': extraction()}
                                  for doc in ('D1', 'D2')])
            out = root / 'out'
            self.assertEqual(self.invoke(paths, out), 1)
            summary = json.loads((out / 'summary.json').read_text(encoding='utf-8'))
            group = summary['groups'][0]
            self.assertEqual(group['missing_document_ids'], ['D2'])
            self.assertEqual(group['quality']['aggregate_exact_accuracy']['value'], .5)

    def test_failed_run_retained(self):
        """Failed run лишається у runtime-метриках і не дає порожніх правильних полів."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths = workspace(root)
            data = run_data(status='failed', first_pass_valid=False)
            data['result'] = None
            data['attempts'][0]['result'] = None
            write_json(paths[1] / 'run_one.json', data)
            out = root / 'out'
            self.assertEqual(self.invoke(paths, out), 1)
            summary = json.loads((out / 'summary.json').read_text(encoding='utf-8'))
            self.assertEqual(summary['groups'][0]['runtime']['status_counts'], {'failed': 1})
            self.assertEqual(summary['groups'][0]['quality']['aggregate_exact_accuracy']['value'], 0)

    def test_existing_output_untouched(self):
        """Повтор у той самий каталог відхиляється без перезапису попередніх звітів."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths = workspace(root)
            out = root / 'out'
            self.assertEqual(self.invoke(paths, out), 0)
            before = {p: digest(p) for p in out.iterdir()}
            self.assertEqual(self.invoke(paths, out), 2)
            self.assertEqual(before, {p: digest(p) for p in before})

    def test_scores_deterministic_across_outputs(self):
        """Зміна output/generated_at не змінює оцінки, конфігурації або details."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths = workspace(root)
            for name in ('a', 'b'):
                self.assertEqual(self.invoke(paths, root / name), 0)
            a = json.loads((root / 'a/summary.json').read_text(encoding='utf-8'))
            b = json.loads((root / 'b/summary.json').read_text(encoding='utf-8'))
            self.assertEqual(a['groups'], b['groups'])
            self.assertEqual((root / 'a/details.json').read_bytes(), (root / 'b/details.json').read_bytes())

    def test_help_and_run_do_not_read_dotenv(self):
        """Навіть реальний запуск оцінки не повинен читати приватний .env."""
        original = Path.read_text

        def guarded(path, *args, **kwargs):
            """Забороняє тесту читати .env, дозволяючи звичайні JSON-фікстури."""
            if path.name == '.env':
                raise AssertionError('private .env read')
            return original(path, *args, **kwargs)

        with tempfile.TemporaryDirectory() as folder, patch.object(Path, 'read_text', guarded):
            root = Path(folder)
            paths = workspace(root)
            self.assertEqual(self.invoke(paths, root / 'out'), 0)
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as captured:
                main(['--help'])
            self.assertEqual(captured.exception.code, 0)

    def test_write_failure_no_completed_summary(self):
        """Помилка публікації звітів повертає 2 і не залишає маркер успішного завершення."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths = workspace(root)
            with patch.object(Path, 'rename', side_effect=OSError('write failed')):
                self.assertEqual(self.invoke(paths, root / 'out'), 2)
            self.assertFalse((root / 'out/summary.json').exists())
            self.assertEqual(list((root / 'out').iterdir()), [])

    def test_markdown_contains_required_conclusions(self):
        """Фінальні висновки показують невідоме й не оголошують автоматичного переможця."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths = workspace(root)
            self.invoke(paths, root / 'out')
            content = (root / 'out/comparison.md').read_text(encoding='utf-8')
            for label in ('Що об’єктивно встановлено', 'Сильні сторони кожної моделі',
                          'Слабкі сторони кожної моделі', 'Що не вдалося встановити',
                          'Чи можна визначити кращу модель', 'Рекомендації для подальших експериментів'):
                self.assertIn(label, content)


if __name__ == '__main__':
    unittest.main()
