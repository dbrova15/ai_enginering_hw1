"""Офлайнові інваріанти: межі, предмет, one-to-one, null та зміст списків."""

import copy
import unittest

from src.evaluation.matching import forced_pairs, optimal_pairs
from src.evaluation.normalization import text
from src.evaluation.policy import SOURCE_CONFLICTS
from src.evaluation.quantities import compare_quantity, quantity
from src.evaluation.scoring import object_list, scalar, score_document, string_list
from tests.evaluation_helpers import component, extraction, parameter


class QuantityTests(unittest.TestCase):
    """Перевіряє еквівалентності й небезпечні близькі записи числових фактів."""

    def test_decimal_comma_and_equivalent_units(self):
        """Десяткова кома й еквівалентні одиниці мають представляти той самий факт."""
        cases = [('1,2', 'V', '1.2', 'В'), ('100', 'uA', '100', 'microamperes'),
                 ('1', 'mA', '1000', 'µA'), ('1', 'kg', '1000', 'g')]
        for lv, lu, rv, ru in cases:
            with self.subTest(lv=lv, lu=lu):
                self.assertEqual(compare_quantity(quantity(lv, lu), quantity(rv, ru)), 'match')

    def test_limits_and_words(self):
        """Словесна нижня межа еквівалентна символу, але не точному числу."""
        self.assertEqual(quantity('>=200', 'm'), quantity('at least 200 meters', 'm'))
        self.assertEqual(quantity('at least a dozen kilos', 'kg'), quantity('>=12', 'kg'))
        self.assertNotEqual(quantity('<100', 'uA'), quantity('100', 'uA'))
        self.assertNotEqual(quantity('>=200', 'm'), quantity('>200', 'm'))

    def test_ranges_signs_and_approximation(self):
        """Діапазон та знак мінуса зберігаються, приблизність не стає точністю."""
        self.assertEqual(quantity('0.3–0.5', 'V'), quantity('0,3-0,5', 'V'))
        self.assertEqual(quantity('−10–−5', 'V')['kind'], 'range')
        self.assertNotEqual(quantity('about 12', 'V'), quantity('12', 'V'))
        self.assertEqual(quantity('14-10', 'V')['kind'], 'conflict')

    def test_unit_conflicts_and_prefixes(self):
        """Зміна mF/uF та суперечливий unit не повинні стати правильним збігом."""
        self.assertNotEqual(quantity('0.1', 'mF'), quantity('0.1', 'uF'))
        self.assertEqual(quantity('12V', 'A')['kind'], 'conflict')
        self.assertEqual(quantity('1mA', 'mA'), quantity('1', 'mA'))

    def test_opaque_configs_and_ambiguous_numbers(self):
        """Номер контакту не розбирається як фізична величина з невідомою одиницею."""
        self.assertEqual(quantity('A4', None)['kind'], 'opaque')
        self.assertEqual(quantity('3x2', None)['kind'], 'opaque')
        self.assertEqual(quantity('1,234', 'V')['kind'], 'opaque')
        self.assertEqual(compare_quantity(quantity('many', None), quantity('few', None)), 'needs_review')


class MatchingTests(unittest.TestCase):
    """Встановлює правильність глобального призначення та облік альтернатив."""

    def test_global_assignment_beats_greedy(self):
        """Локально найсильніше ребро не має зменшувати кількість правильних пар."""
        candidates = {(0, 0): 5, (0, 1): 4, (1, 0): 4}
        pairs, objective = optimal_pairs(2, 2, candidates)
        self.assertEqual(pairs, [(0, 1), (1, 0)])
        self.assertEqual(objective, (2, 8))

    def test_ties_need_review(self):
        """Два рівноцінні компоненти не отримують випадкові підтверджені пари."""
        result = forced_pairs(2, 2, {(i, j): 4 for i in range(2) for j in range(2)})
        self.assertEqual(result['pairs'], [])
        self.assertEqual(len(result['review_edges']), 4)

    def test_weight_priority_and_scale(self):
        """За однакової кількості пар виграє сильніший доказ; список не перебирається факторіально."""
        self.assertEqual(forced_pairs(1, 2, {(0, 0): 5, (0, 1): 4})['pairs'], [(0, 0)])
        result = forced_pairs(35, 35, {(i, i): 4 for i in range(35)})
        self.assertEqual(len(result['pairs']), 35)


class ScoringTests(unittest.TestCase):
    """Перевіряє різницю між identity, повним фактом та непідтвердженим текстом."""

    def test_component_order_does_not_matter(self):
        """Перестановка масиву повинна залишати perfect score без зміни сутностей."""
        gold = [component('Arduino UNO', 'UNO'), component('relay')]
        result = object_list('components', gold, list(reversed(gold)))
        self.assertTrue(result['exact'])
        self.assertEqual(result['full_fact']['tp'], 2)

    def test_predicted_duplicates_penalized(self):
        """Повтор тієї самої деталі не дає другий TP і стає зайвим прогнозом."""
        gold = [component()]
        result = object_list('components', gold, gold * 2)
        self.assertEqual(result['identity'], dict(tp=1, fp=1, fn=0, expected=1, predicted=2))
        self.assertFalse(result['exact'])

    def test_golden_duplicate_is_review(self):
        """Повтор еталона не приховується автоматичним видаленням під час scoring."""
        result = object_list('components', [component(), component()], [component()])
        self.assertTrue(result['duplicate_golden'])
        self.assertFalse(result['exact'])

    def test_similar_components_not_merged(self):
        """Один загальний резистор не може закрити дві деталі з різними ролями."""
        gold = [component('resistor', role='pull-up'), component('resistor', role='threshold')]
        result = object_list('components', gold, [component('resistor')])
        self.assertEqual(result['identity']['tp'], 0)
        self.assertTrue(result['ambiguous_pairing_groups'])

    def test_attributes_and_schematic_models(self):
        """Сутність можна впізнати, але непідтверджена модель чи виробник лишаються помилками."""
        predicted = component('relay', model='K1', manufacturer='Unknown')
        result = object_list('components', [component()], [predicted])
        self.assertEqual(result['identity']['tp'], 1)
        self.assertEqual(result['full_fact']['tp'], 0)
        self.assertEqual(result['pairs'][0]['checks'][1]['verdict'], 'mismatch')

    def test_parameter_subject_is_required(self):
        """12 В батареї не дорівнює 12 В реле."""
        result = object_list('technical_parameters', [parameter()], [parameter(subject='relay')])
        self.assertEqual(result['full_fact']['tp'], 0)
        self.assertEqual(result['full_fact']['fn'], 1)

    def test_parameter_context_and_bounds(self):
        """Бажаний показник не є виміряним; нижня межа не є точним значенням."""
        gold = [parameter('>=200', 'm', 'radio', 'desired control distance')]
        good = [parameter('at least 200 meters', 'm', 'radio', 'desired control distance')]
        self.assertTrue(object_list('technical_parameters', gold, good)['exact'])
        for name in ('measured control distance', 'control distance'):
            wrong = [parameter('200', 'm', 'radio', name)]
            self.assertEqual(object_list('technical_parameters', gold, wrong)['full_fact']['tp'], 0)

    def test_string_sets_and_namespaces(self):
        """Wi-Fi/Wifi та I2C/I²C еквівалентні; мовам не зараховується інше поле."""
        result = string_list('interfaces_protocols', ['Wi-Fi', 'I2C'], ['I²C', 'Wifi', 'Wi-Fi'])
        self.assertTrue(result['exact'])
        self.assertEqual(result['full_fact']['tp'], 2)
        doc = score_document(extraction(software_tools=['Python']), extraction(interfaces_protocols=['Python']))
        self.assertEqual(doc['software_tools']['full_fact']['fn'], 1)
        self.assertEqual(doc['interfaces_protocols']['full_fact']['fp'], 1)

    def test_null_text_and_periphrasis(self):
        """Null не дорівнює Unknown; перефразування не дає автоматичної точності."""
        self.assertEqual(scalar('x', None, None)['verdict'], 'match')
        self.assertEqual(scalar('x', None, 'Unknown')['verdict'], 'mismatch')
        self.assertEqual(scalar('x', 'clock', 'device showing time')['verdict'], 'needs_review')
        self.assertEqual(text('  HELLO   world. '), 'hello world')
        self.assertNotEqual(text('C++'), text('C'))

    def test_missing_prediction_never_perfect(self):
        """Навіть порожній еталонний список не дає exact при відсутньому прогнозі."""
        fields = score_document(extraction(), None)
        self.assertEqual(len(fields), 8)
        self.assertFalse(any(item['exact'] for item in fields.values()))

    def test_hr0207_conflict_not_alias(self):
        """Обидва суперечливі маркування однаково потребують перегляду, а не виправлення golden."""
        gold = [component('Стабілізатор напруги керування реле')]
        for model in ('lm7508', 'lm7805'):
            pred = copy.deepcopy(gold)
            pred[0]['model'] = model
            result = object_list('components', gold, pred, SOURCE_CONFLICTS['HR-0207'])
            self.assertEqual(result['pairs'][0]['checks'][1]['verdict'], 'needs_review')
            self.assertEqual(result['full_fact']['tp'], 0)


if __name__ == '__main__':
    unittest.main()
