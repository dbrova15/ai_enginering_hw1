"""Додаткові властивості: matching проти перебору та чесність багатогрупового звіту."""

import itertools
import random
import tempfile
import unittest
from pathlib import Path

from src.evaluation.loading import load_dataset
from src.evaluation.matching import forced_pairs, optimal_pairs
from src.evaluation.normalization import alias
from src.evaluation.runner import evaluate
from src.evaluation.scoring import object_list
from tests.evaluation_helpers import component, run_data, workspace, write_json


class InvariantTests(unittest.TestCase):
    """Порівнює алгоритм з незалежним розв’язком на малих випадках і перестановками."""

    def test_matching_against_exhaustive_small_graphs(self):
        """Випадкові графи 3×3 мають той самий оптимум і обов’язкові ребра, що повний перебір."""
        generator = random.Random(4815)
        for _ in range(25):
            edges = {(i, j): generator.randint(1, 5) for i in range(3) for j in range(3)
                     if generator.random() > .3}
            solutions = []
            for choices in itertools.product(range(-1, 3), repeat=3):
                pairs = {(i, j) for i, j in enumerate(choices) if j >= 0}
                if len({j for _, j in pairs}) != len(pairs) or not pairs <= edges.keys():
                    continue
                solutions.append(((len(pairs), sum(edges[p] for p in pairs)), pairs))
            best = max(obj for obj, _ in solutions)
            winners = [pairs for obj, pairs in solutions if obj == best]
            expected_forced = set.intersection(*winners)
            self.assertEqual(optimal_pairs(3, 3, edges)[1], best)
            self.assertEqual(set(forced_pairs(3, 3, edges)['pairs']), expected_forced)

    def test_all_permutations_preserve_ambiguous_score(self):
        """Навіть неоднозначність не повинна зникати через зміну порядку списків."""
        gold = [component('resistor', role='pull-up'), component('resistor', role='threshold')]
        pred = [component('resistor'), component('capacitor')]
        scores = set()
        for left in itertools.permutations(gold):
            for right in itertools.permutations(pred):
                actual = object_list('components', list(left), list(right))
                scores.add((actual['identity']['tp'], actual['full_fact']['fp'],
                            actual['full_fact']['fn'], len(actual['ambiguous_pairing_groups'])))
        self.assertEqual(len(scores), 1)

    def test_aliases_have_expected_namespace(self):
        """Протокольний alias не переходить приховано у software namespace."""
        self.assertEqual(alias('WiFi', 'interfaces_protocols'), 'wi-fi')
        self.assertEqual(alias('WiFi', 'software_tools'), 'wifi')

    def test_report_examples_cover_both_groups(self):
        """Перші п’ять помилок не можуть усі походити з однієї конфігурації."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            golden, runs, manifest, rules = workspace(root)
            write_json(runs / 'run_one.json', run_data(result={'bad': True}))
            write_json(runs / 'run_two.json', run_data(provider='second', result={'bad': True}))
            summary, _ = evaluate(golden, [runs], root / 'out', manifest, rules)
            report = (root / 'out/comparison.md').read_text(encoding='utf-8')
            examples = report.split('## Приклади розбіжностей із еталоном')[1].split('## Висновок')[0]
            for group in summary['groups']:
                self.assertIn(group['group_id'][:8], examples)

    def test_source_conflict_requires_fingerprint(self):
        """Registry HR-0207 не використовується як доказ, коли TXT не відповідає fingerprint."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            golden, runs, manifest, rules = workspace(root)
            source = root / 'source.txt'
            source.write_text('different article', encoding='utf-8')
            write_json(manifest, [{'id': 'HR-0207', 'text_path': 'source.txt'}])
            data = load_dataset(golden, [runs], manifest, rules)
            self.assertFalse(data.source_conflicts['HR-0207']['fingerprint_valid'])
            self.assertTrue(any('застарів' in warning for warning in data.warnings))


if __name__ == '__main__':
    unittest.main()
