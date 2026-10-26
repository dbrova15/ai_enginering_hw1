"""Валідація v2 golden/runs і планового coverage, без відновлення raw_content."""

import hashlib
import math
from pathlib import Path

from pydantic import ValidationError

from src.document_runner import TEXT_PREPARATION_VERSION, prepare_article_text
from src.evaluation.loading import _inspect_result, read_json
from src.evaluation.models import EvaluationError, RunRecord, canonical_json, digest
from src.schemas import SCHEMA_V2


def validate(value) -> dict | None:
    """Повертає лише структурно валідний canonical v2 result; невдалий — None."""
    try:
        return SCHEMA_V2.model.model_validate(value).model_dump(mode='json')
    except ValidationError:
        return None


def load_golden(path: Path, strict: bool) -> tuple[dict, bool]:
    """Читає незалежні еталони v2; approved не виводиться з правильного JSON."""
    rows = read_json(path)
    if not isinstance(rows, list) or not rows:
        raise EvaluationError('Golden v2 має бути непорожнім масивом.')
    golden = {}
    for row in rows:
        if not isinstance(row, dict) or row.get('schema_version') != 'v2':
            raise EvaluationError('Golden повинен явно належати Schema v2.')
        doc = row.get('document_id')
        if not isinstance(doc, str) or not doc or doc in golden or validate(row.get('expected')) is None:
            raise EvaluationError('Повторний/неправильний ID або expected у Golden v2.')
        if not isinstance(row.get('annotation_status'), str):
            raise EvaluationError('Відсутній статус людської розмітки.')
        golden[doc] = {**row, 'expected': validate(row['expected'])}
    pending = [doc for doc, row in golden.items() if row['annotation_status'] != 'approved']
    if strict and pending:
        raise EvaluationError('Strict v2 потребує approved: ' + ', '.join(sorted(pending)))
    return golden, bool(pending)


def load_run(path: Path, plan: dict) -> RunRecord:
    """Перевіряє metadata і result саме v2; ніякого model-specific виправлення тегів."""
    row = read_json(path)
    if not isinstance(row, dict) or row.get('schema_version') != 'v2':
        raise EvaluationError('evaluate_v2.py приймає лише Schema v2.')
    if row.get('schema_sha256') != SCHEMA_V2.sha256:
        raise EvaluationError(f'Невідома JSON Schema hash: {path}')
    required = ('document_id', 'provider', 'requested_model', 'experiment_id', 'source_sha256',
                'input_text_sha256', 'text_preparation_version')
    if any(not isinstance(row.get(k), str) or not row[k] for k in required):
        raise EvaluationError(f'Неповні v2 metadata: {path}')
    prompt, sampling = row.get('prompt'), row.get('sampling')
    if not isinstance(prompt, dict) or prompt.get('namespace') != 'schema_v2' or not all(
        isinstance(prompt.get(k), str) and prompt[k] for k in ('version', 'sha256')):
        raise EvaluationError('Потрібні namespace/version/hash v2 промпту.')
    if not isinstance(sampling, dict) or not all(k in sampling for k in ('temperature', 'top_p')):
        raise EvaluationError('Відсутній sampling v2.')
    if any(isinstance(sampling[k], bool) or not isinstance(sampling[k], (int, float)) or
           not math.isfinite(sampling[k]) for k in ('temperature', 'top_p')) or not (
            0 <= sampling['temperature'] <= 2 and 0 < sampling['top_p'] <= 1):
        raise EvaluationError('Неприпустимий sampling v2.')
    if row.get('kind') != 'primary':
        raise EvaluationError('Probe/warmup не можна включати у primary оцінювання.')
    if row['document_id'] not in plan['planned_ids']:
        raise EvaluationError('Run ID відсутній у planned IDs.')
    checks = {'experiment_id': row['experiment_id'], 'provider': row['provider'],
              'model': row['requested_model'], 'sampling': sampling, 'schema_sha256': row['schema_sha256'],
              'prompt_namespace': prompt['namespace'], 'prompt_version': prompt['version'],
              'prompt_sha256': prompt['sha256']}
    if any(plan.get(k) != v for k, v in checks.items()):
        raise EvaluationError('Run не відповідає конфігурації experiment manifest.')
    attempts = row.get('attempts', [])
    if not isinstance(attempts, list) or any(not isinstance(a, dict) for a in attempts):
        raise EvaluationError('Невалідні attempts.')
    result, problems, first = _inspect_result(row, attempts, validator=validate)
    config = {k: row.get(k) for k in ('schema_version', 'schema_sha256', 'provider', 'requested_model',
                                     'experiment_id', 'prompt', 'sampling', 'limits', 'text_preparation_version')}
    config['returned_model'] = attempts[-1].get('returned_model') if attempts else None
    return RunRecord(path.resolve(), row, config, result, first, problems)


def load_runs(roots: list[Path], manifest_path: Path) -> tuple[dict, dict, dict, list]:
    """Групує конфігурації з planned ID, перевіряє source/prepared fingerprints та дублікати."""
    manifest = read_json(manifest_path)
    if not isinstance(manifest, list) or any(not isinstance(m, dict) or not isinstance(m.get('id'), str)
                                             for m in manifest):
        raise EvaluationError('Manifest повинен бути масивом.')
    meta = {m['id']: m for m in manifest}
    if len(meta) != len(manifest):
        raise EvaluationError('Повторні ID у manifest.')
    groups, plans, fingerprints, warnings = {}, {}, {}, []
    for root in sorted(set(p.resolve() for p in roots)):
        plan_path = root / 'experiment_manifest.json'
        plan = read_json(plan_path)
        ids = plan.get('planned_ids') if isinstance(plan, dict) else None
        if not isinstance(plan, dict) or plan.get('schema_version') != 'v2' or not isinstance(ids, list) or not ids or any(
            not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids)):
            raise EvaluationError('Потрібен валідний v2 experiment_manifest з planned_ids.')
        if plan.get('planned_count') != len(ids):
            raise EvaluationError('planned_count не відповідає planned_ids.')
        if set(ids) - meta.keys():
            raise EvaluationError('Unknown planned ID у manifest.')
        fingerprints[str(plan_path)] = digest(plan_path)
        paths = sorted(root.glob('run_*.json'))
        if not paths:
            raise EvaluationError('Немає primary runs; experiment ще не можна оцінити.')
        root_groups = set()
        for path in paths:
            run = load_run(path, plan)
            # Відсутній returned_model у transport failure не створює інший
            # експеримент: requested model і settings лишаються тими самими.
            config = {k: v for k, v in run.config.items() if k != 'returned_model'}
            group_id = hashlib.sha256(canonical_json(config).encode('utf-8')).hexdigest()
            root_groups.add(group_id)
            group = groups.setdefault(group_id, [])
            if any(r.document_id == run.document_id for r in group):
                raise EvaluationError(f'Дублікат primary ID: {run.document_id}')
            group.append(run)
            plans[group_id] = plan
            fingerprints[str(path)] = digest(path)
            entry = meta.get(run.document_id, {})
            if 'text_path' in entry:
                source = (manifest_path.parent / entry['text_path']).resolve()
                _check_source(run, source)
                fingerprints[str(source)] = digest(source)
            else:
                warnings.append(f'{run.document_id}: source fingerprint недоступний у manifest')
        if len(root_groups) != 1:
            raise EvaluationError('Змішані конфігурації в одному experiment каталозі.')
    return groups, plans, fingerprints, warnings


def _check_source(run: RunRecord, source: Path) -> None:
    """Звіряє саме TXT і prepared user text, не metadata category/topic/language."""
    original = source.read_bytes().decode('utf-8')
    actual = hashlib.sha256(prepare_article_text(original).encode('utf-8')).hexdigest()
    if (digest(source) != run.data['source_sha256'] or actual != run.data['input_text_sha256'] or
            run.data['text_preparation_version'] != TEXT_PREPARATION_VERSION):
        raise EvaluationError(f'Невідповідний source/prepared input: {run.document_id}')
