"""Перевірка planned/received/missing для основної матриці без викликів моделей."""

import argparse
import json
from pathlib import Path

from src.evaluation.loading import read_json
from src.evaluation.models import EvaluationError, digest
from src.schemas import SCHEMA_V2


def check_matrix(plan_path: Path, project_root: Path) -> dict:
    """Звіряє 120 planned пар, hashes промптів і фактично збережені primary ID.

    Не вважає невдалий run відсутнім і не обирає найкращий повтор. Probe,
    дублікати та невідповідна конфігурація — помилка, а не завершення матриці.
    Prompt-v2 без файла лишається not_written; нічого не генерується.
    """
    plan = read_json(plan_path)
    rows = plan['configurations']
    if len(rows) != 8 or sum(r['planned_count'] for r in rows) != 120:
        raise EvaluationError('Основний plan має містити 8 конфігурацій і 120 planned primary.')
    if set(plan['golden_ids']) & set(plan['development_ids']):
        raise EvaluationError('D/G leakage у plan.')
    combinations = {(r['provider'], r['model'], r['prompt_version'], r['sampling']['temperature'],
                     r['sampling']['top_p']) for r in rows}
    expected = {(provider, model, prompt, temperature, 1)
                for provider, model in [('openai', 'gpt-4o-mini'), ('ollama', 'llama3.2:3b')]
                for prompt in ['v1', 'v2'] for temperature in [0, .7]}
    if combinations != expected:
        raise EvaluationError('Матриця не відповідає 2 моделям × 2 промптам × T0/T07.')
    result, seen = [], set()
    for row in rows:
        ids = row['planned_ids']
        required_ids = ([r['document_id'] for r in plan['inputs']]
                        if row['prompt_version'] == 'v1' and row['sampling']['temperature'] == 0
                        else plan['golden_ids'])
        if set(ids) != set(required_ids):
            raise EvaluationError('Неправильна N/G вибірка конфігурації.')
        if len(set(ids)) != len(ids) or len(ids) != row['planned_count'] or row['experiment_id'] in seen:
            raise EvaluationError('Дублікати ID/config або неправильний planned_count.')
        seen.add(row['experiment_id'])
        if row['schema_sha256'] != SCHEMA_V2.sha256:
            raise EvaluationError('Schema hash plan не відповідає реалізації.')
        prompt = project_root / 'prompts/schema_v2' / (row['prompt_version'] + '.txt')
        if row['prompt_sha256'] is not None and digest(prompt) != row['prompt_sha256']:
            raise EvaluationError('Prompt hash plan змінився.')
        observed = set()
        for path in sorted((project_root / 'results/schema_v2' / row['experiment_id']).glob('run_*.json')):
            run = read_json(path)
            doc = run.get('document_id')
            if run.get('kind') != 'primary' or doc in observed or doc not in ids:
                raise EvaluationError('Duplicate/unknown/non-primary у конфігурації.')
            if (run.get('experiment_id') != row['experiment_id'] or run.get('schema_sha256') != row['schema_sha256']
                    or run.get('sampling') != row['sampling'] or run.get('provider') != row['provider']
                    or run.get('requested_model') != row['model']
                    or run.get('prompt', {}).get('sha256') != row['prompt_sha256']):
                raise EvaluationError('Run metadata не відповідають plan.')
            observed.add(doc)
        missing = sorted(set(ids) - observed)
        result.append({'experiment_id': row['experiment_id'], 'planned': len(ids), 'received': len(observed),
                       'missing_ids': missing, 'status': 'partial' if missing else 'completed'})
    return {'schema_version': 'v2', 'planned_primary': 120,
            'received_primary': sum(r['received'] for r in result), 'configurations': result}


def main() -> int:
    """Друкує coverage JSON; code 1 означає missing, не помилку моделі."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=Path('results/schema_v2/plan.json'))
    args = parser.parse_args()
    try:
        result = check_matrix(args.plan, Path(__file__).resolve().parents[2])
    except (EvaluationError, OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f'Помилка plan: {exc}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(result['received_primary'] != 120)


if __name__ == '__main__':
    raise SystemExit(main())
