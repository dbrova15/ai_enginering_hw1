"""Однакові іменовані контролі для вимірювання старого й нового evaluator офлайново."""

import argparse
import json
from pathlib import Path

from src.evaluation.policy import POLICY_VERSION, SOURCE_CONFLICTS
from src.evaluation.scoring import object_list, scalar

CONTROLS_PATH = Path(__file__).parent / 'fixtures/semantic_controls.json'


def evaluate_case(case: dict) -> str:
    """Перетворює відповідь evaluator на match/mismatch/review без зміни критеріїв.

    Для object lists одиниця контролю — один повний факт. Неідентифікований
    позитив означає false negative; для негативів важливе недопущення match.
    """
    field = case['field']
    if field not in ('components', 'technical_parameters'):
        return scalar(field, case['expected'], case['predicted'])['verdict']
    conflict = SOURCE_CONFLICTS['HR-0207'] if case.get('source_conflict') else None
    scored = object_list(field, [case['expected']], [case['predicted']], conflict)
    if scored['full_fact']['tp'] == 1:
        return 'match'
    if scored['pairs']:
        pair = scored['pairs'][0]
        if 'verdict' in pair:
            return pair['verdict']
        return 'mismatch' if any(c['verdict'] == 'mismatch' for c in pair['checks']) else 'needs_review'
    return 'needs_review' if scored.get('candidate_pairs') else 'missing'


def run_controls() -> dict:
    """Рахує FN/FP на фіксованих прикладах; не використовує Golden Set як aliases."""
    cases = json.loads(CONTROLS_PATH.read_text(encoding='utf-8'))
    results = [{**case, 'actual': evaluate_case(case)} for case in cases]
    positives = [c for c in results if c['verdict'] == 'match']
    negatives = [c for c in results if c['verdict'] != 'match']
    return {'policy_version': POLICY_VERSION, 'positive_count': len(positives),
            'negative_count': len(negatives), 'false_negatives': sum(c['actual'] != 'match' for c in positives),
            'false_positives': sum(c['actual'] == 'match' for c in negatives), 'cases': results}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Офлайнові контрольні факти evaluator.')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(run_controls(), stream, ensure_ascii=False, indent=2)
