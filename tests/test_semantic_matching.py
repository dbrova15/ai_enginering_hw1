"""Регресії підтверджених перекладів і захист від хибнопозитивних semantic matches."""

import itertools
import json
import unittest

from src.evaluation.metrics import aggregate_quality
from src.evaluation.quantities import quantity
from src.evaluation.scoring import object_list, scalar, score_document
from tests.evaluation_helpers import component, extraction, parameter
from tests.semantic_controls import CONTROLS_PATH, evaluate_case, run_controls


class SemanticControlsTests(unittest.TestCase):
    """Виконує один і той самий документований набір фактів незалежно від моделі."""

    def test_positive_controls(self):
        """Усі підтверджені позитивні приклади мають бути повними фактними matches."""
        controls = run_controls()
        for case in controls['cases']:
            if case['verdict'] == 'match':
                with self.subTest(case=case['id']):
                    self.assertEqual(case['actual'], 'match')
        self.assertEqual(controls['positive_count'], 19)

    def test_negative_controls_no_false_positives(self):
        """Різні пристрої, ролі, одиниці та моделі не стають правильними через однакове число."""
        controls = run_controls()
        self.assertEqual(controls['false_positives'], 0)
        for case in controls['cases']:
            if case['verdict'] != 'match':
                with self.subTest(case=case['id']):
                    self.assertNotEqual(case['actual'], 'match')

    def test_review_controls_not_reclassified_as_errors(self):
        """Часткові твердження, невідомі subject і конфлікт джерела залишаються review."""
        cases = json.loads(CONTROLS_PATH.read_text(encoding='utf-8'))
        for case in cases:
            if case['verdict'] == 'needs_review':
                with self.subTest(case=case['id']):
                    self.assertEqual(evaluate_case(case), 'needs_review')


class SemanticInvariantTests(unittest.TestCase):
    """Перевіряє небезпечні взаємодії між identity, атрибутами й кандидатами."""

    def test_candidate_cannot_steal_confirmed_pair(self):
        """Нечіткий subject розглядається лише після закриття доказових пар."""
        gold = [parameter(subject='relay'), parameter(subject='Tilt sensor module')]
        pred = [parameter(subject='relay'), parameter(subject='Voltage')]
        result = object_list('technical_parameters', gold, pred)
        self.assertEqual(result['full_fact']['tp'], 1)
        self.assertEqual(len(result['candidate_pairs']), 1)
        self.assertFalse(result['candidate_pairs'][0]['identity_confirmed'])

    def test_unknown_subject_different_number_is_conditional(self):
        """Різні числа при невідомому предметі не є доведеною помилкою того самого факту."""
        result = object_list('technical_parameters', [parameter(subject='relay')],
                             [parameter('24', 'V', 'Voltage')])
        self.assertEqual(result['fact_assessment']['confirmed_contradictions'], 0)
        self.assertEqual(result['candidate_pairs'][0]['verdict'], 'needs_review')
        self.assertTrue(result['candidate_pairs'][0]['conditional_disagreements'])
        self.assertFalse(any(c['verdict'] == 'mismatch' for c in result['checks']))

    def test_confirmed_wrong_value_is_contradiction(self):
        """Той самий предмет і тип величини з іншим числом дає mismatch, а не review."""
        result = object_list('technical_parameters', [parameter()], [parameter('24')])
        self.assertEqual(result['pairs'][0]['verdict'], 'mismatch')
        self.assertEqual(result['fact_assessment']['confirmed_contradictions'], 1)

    def test_candidates_with_ties_stay_ambiguous(self):
        """Дві можливі прив’язки одного невизначеного прогнозу не обираються випадково."""
        result = object_list('technical_parameters', [parameter(subject='relay'), parameter(subject='battery')],
                             [parameter(subject='Voltage')])
        self.assertEqual(result['full_fact']['tp'], 0)
        self.assertTrue(result['ambiguous_pairing_groups'])
        self.assertEqual(result['candidate_pairs'], [])

    def test_semantic_permutation_invariance(self):
        """Порядок перекладених параметрів не змінює TP/FN/FP чи число кандидатів."""
        gold = [parameter('5', 'В', 'Модуль датчика нахилу', 'Робоча напруга'), parameter('12', 'V', 'relay')]
        pred = [parameter('5 volts', None, 'Tilt sensor module', 'Operating voltage'), parameter('12', 'V', 'Voltage')]
        values = set()
        for left in itertools.permutations(gold):
            for right in itertools.permutations(pred):
                result = object_list('technical_parameters', list(left), list(right))
                values.add((result['full_fact']['tp'], result['full_fact']['fp'], result['full_fact']['fn']))
        self.assertEqual(values, {(1, 1, 1)})

    def test_module_and_ball_sensor_not_same_even_shared_model(self):
        """Загальний модельний код не зливає модуль та окремий чутливий елемент."""
        result = object_list('components', [component('Tilt sensor module', 'SW-520D')],
                             [component('Ball tilt sensor', 'SW-520D')])
        self.assertEqual(result['identity']['tp'], 0)

    def test_model_token_not_substring(self):
        """ABC1 не збігається з ABC10 через просту перевірку входження рядка."""
        result = object_list('components', [component('sensor', 'ABC1')],
                             [component('ABC10 sensor')])
        self.assertEqual(result['identity']['tp'], 0)

    def test_schematic_or_generic_label_is_not_model_identity(self):
        """R1 та microchip у model не можуть об’єднати два невідомі різні компоненти."""
        for model in ('R1', 'microchip', 'used', 'N/A'):
            result = object_list('components', [component('unclassified part one', model)],
                                 [component('unclassified part two', model)])
            self.assertEqual(result['identity']['tp'], 0, model)

    def test_multilingual_context_is_preserved(self):
        """Виділення українського/російського статусу не втрачає номінальність величини."""
        gold = parameter('5', 'В', 'Реле', 'Номінальна напруга')
        good = parameter('5', 'V', 'relay', 'Nominal voltage')
        wrong = parameter('5', 'V', 'relay', 'Measured voltage')
        self.assertEqual(object_list('technical_parameters', [gold], [good])['full_fact']['tp'], 1)
        self.assertEqual(object_list('technical_parameters', [gold], [wrong])['full_fact']['tp'], 0)

    def test_identity_from_full_model_name_does_not_repair_attribute(self):
        """Багатослівна явна модель відновлює identity навіть за хибного model-поля, без full_fact TP."""
        cases = [('controller board', 'Wemos D1 mini', 'Wemos D1 mini', 'microcontroller'),
                 ('LCD display', '1602A', 'LCD 1602A', None),
                 ('RTC module', 'DS1302', 'RTC DS1302', '5-pin version')]
        for gold_name, model, predicted_name, wrong in cases:
            with self.subTest(model=model):
                result = object_list('components', [component(gold_name, model)], [component(predicted_name, wrong)])
                self.assertEqual(result['identity']['tp'], 1)
                self.assertEqual(result['full_fact']['tp'], 0)

    def test_known_board_revision_is_partial_not_different_board(self):
        """Uno без ревізії не є Mega; явний UNO rev.3 у назві дозволяє впізнати плату."""
        result = object_list('components', [component('Плата Arduino UNO', 'UNO rev.3')],
                             [component('Arduino UNO rev.3')])
        self.assertEqual(result['identity']['tp'], 1)
        self.assertEqual(result['full_fact']['tp'], 0)

    def test_unproven_manufacturer_is_not_confirmed_contradiction(self):
        """Golden null забороняє full_fact TP, але сам не доводить хибність виробника у джерелі."""
        result = object_list('components', [component('relay')], [component('relay', manufacturer='Acme')])
        self.assertEqual(result['identity']['tp'], 1)
        self.assertEqual(result['full_fact']['tp'], 0)
        self.assertEqual(result['fact_assessment']['confirmed_contradictions'], 0)
        self.assertEqual(result['fact_assessment']['unsupported_attribute_pairs'], 1)

    def test_dimensions_and_angle_effective_units(self):
        """Явна одиниця в value підтверджує розмірність без дублювання в окремому unit."""
        self.assertEqual(quantity('3.2 cm x 1.4 cm', None), quantity('3,2 × 1,4', 'см'))
        self.assertEqual(quantity('45–130°', None), quantity('45 to 130', 'degrees'))
        self.assertNotEqual(quantity('3.2 x 1.4', 'cm'), quantity('3.2 x 1.4', 'mm'))

    def test_known_property_requires_physical_quantity(self):
        """Збіг непрозорого опису або неправильної розмірності не дає фактний TP."""
        for fact in (parameter('real-time monitoring', 'uA', 'relay', 'current consumption'),
                     parameter('3.2 x 1.4', 'V', 'Module circuit board', 'Board size')):
            result = object_list('technical_parameters', [fact], [fact])
            self.assertEqual(result['full_fact']['tp'], 0)
            self.assertEqual(result['pairs'][0]['verdict'], 'needs_review')

    def test_unknown_extra_words_are_not_ignored(self):
        """Невідома функція або заперечення не відкидається під час canonical translation."""
        self.assertNotEqual(scalar('main_subject', 'Arduino Uno', 'Arduino Uno with Wi-Fi')['verdict'], 'match')
        self.assertNotEqual(scalar('purpose', 'Вимірювання температури', 'No temperature measurement')['verdict'], 'match')

    def test_fact_counts_include_missing_prediction(self):
        """Невідомий прогноз зберігає expected у missing діагностиках і консервативних FN."""
        fields = score_document(extraction(components=[component()]), None)
        aggregate = aggregate_quality([{'fields': fields}])
        self.assertEqual(aggregate['fact_assessment']['components']['missing'], 1)


if __name__ == '__main__':
    unittest.main()
