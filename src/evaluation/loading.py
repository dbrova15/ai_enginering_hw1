"""Читання входів оцінювача без мережі, виправлення еталонів чи API-викликів."""

import json
import platform
from pathlib import Path

import pydantic
from pydantic import ValidationError

from src.evaluation import __version__
from src.evaluation import policy
from src.evaluation.models import Dataset, EvaluationError, RunRecord, canonical_json, digest
from src.schema import ExtractionResult


def _reject_constant(value: str) -> None:
    """Забороняє нестандартні NaN/Infinity у JSON, щоб вони не псували метрики."""
    raise EvaluationError(f'Неприпустима JSON-константа: {value}')


def read_json(path: Path):
    """Читає UTF-8 JSON; у діагностиці показує шлях, а не довільний вміст файла."""
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'), parse_constant=_reject_constant)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvaluationError(f'Не вдалося прочитати UTF-8 JSON: {path}') from exc


def valid_result(value) -> dict | None:
    """Перевіряє об’єкт чинною Schema v1; не намагається розібрати raw_content."""
    try:
        return ExtractionResult.model_validate(value).model_dump(mode='json')
    except ValidationError:
        return None


def load_golden(path: Path, strict: bool) -> tuple[dict, bool]:
    """Перевіряє унікальність і структуру еталонів та право на strict-оцінювання."""
    rows = read_json(path)
    if not isinstance(rows, list) or not rows:
        raise EvaluationError('Golden set повинен бути непорожнім JSON-масивом.')
    golden = {}
    for row in rows:
        if isinstance(row, dict) and row.get('schema_version') == 'v2':
            raise EvaluationError('Golden Schema v2 потребує evaluate_v2.py; evaluate.py є історичним v1.')
        if not isinstance(row, dict) or not isinstance(row.get('document_id'), str):
            raise EvaluationError('Некоректний document_id у golden set.')
        doc = row['document_id']
        if not doc.strip() or doc in golden or valid_result(row.get('expected')) is None:
            raise EvaluationError(f'Дублікат ID або невалідний expected: {doc}')
        if not isinstance(row.get('annotation_status'), str):
            raise EvaluationError(f'Відсутній annotation_status: {doc}')
        golden[doc] = row
    pending = [f'{doc}:{row["annotation_status"]}' for doc, row in golden.items()
               if row['annotation_status'] != policy.APPROVED_STATUS]
    if strict and pending:
        raise EvaluationError('Strict golden відхилено: ' + ', '.join(sorted(pending)))
    return golden, bool(pending)


def load_run(path: Path) -> RunRecord:
    """Перевіряє envelope та класифікує непридатний прогноз без прихованого repair."""
    row = read_json(path)
    keys = ('document_id', 'provider', 'requested_model', 'schema_version')
    if not isinstance(row, dict) or any(not isinstance(row.get(k), str) or not row[k] for k in keys):
        raise EvaluationError(f'Не можна визначити конфігурацію/ID: {path}')
    if row['schema_version'] != 'v1':
        raise EvaluationError('Історичний evaluate.py підтримує лише Schema v1; для v2 використайте evaluate_v2.py.')
    prompt, sampling = row.get('prompt'), row.get('sampling')
    if not isinstance(prompt, dict) or any(not isinstance(prompt.get(k), str) or not prompt[k]
                                           for k in ('version', 'sha256')):
        raise EvaluationError(f'Некоректні метадані промпту: {path}')
    if not isinstance(sampling, dict) or not all(k in sampling for k in ('temperature', 'top_p')):
        raise EvaluationError(f'Відсутній sampling: {path}')
    if any(isinstance(sampling[k], bool) or not isinstance(sampling[k], (int, float))
           for k in ('temperature', 'top_p')):
        raise EvaluationError(f'Некоректні типи sampling: {path}')
    attempts = row.get('attempts', [])
    if not isinstance(attempts, list) or any(not isinstance(a, dict) for a in attempts):
        raise EvaluationError(f'Некоректні attempts: {path}')
    returned = attempts[-1].get('returned_model') if attempts else None
    if returned is not None and not isinstance(returned, str):
        raise EvaluationError(f'Некоректний returned_model: {path}')
    if row.get('limits') is not None and not isinstance(row['limits'], dict):
        raise EvaluationError(f'Некоректні limits: {path}')
    config = {k: row[k] for k in keys if k != 'document_id'}
    config.update(returned_model=returned, prompt=prompt, sampling=sampling, limits=row.get('limits'))
    canonical_json(config)
    result, problems, first = _inspect_result(row, attempts)
    return RunRecord(path, row, config, result, first, problems)


def _inspect_result(row: dict, attempts: list, validator=valid_result) -> tuple:
    """Звіряє статуси й структуровані результати спроб; unknown не стає false."""
    result = validator(row.get('result'))
    status = row.get('status')
    problems = []
    if status not in ('success', 'repaired', 'failed'):
        problems.append('unknown_status')
        result = None
    if status == 'failed':
        if row.get('result') is not None:
            problems.append('failed_with_result')
        result = None
    elif result is None:
        problems.append('invalid_result')
    first = None
    if attempts and 'result' in attempts[0]:
        first = validator(attempts[0]['result']) is not None
    claimed = row.get('first_pass_valid')
    if first is not None and (not isinstance(claimed, bool) or claimed != first):
        problems.append('first_pass_conflict')
    if status == 'repaired' and (len(attempts) != 2 or first is not False):
        problems.append('repair_status_conflict')
    if status == 'success' and (len(attempts) > 1 or first is False):
        problems.append('success_status_conflict')
    if result is not None and attempts and 'result' in attempts[-1]:
        if validator(attempts[-1]['result']) != result:
            problems.append('final_attempt_conflict')
            result = None
    return result, problems, first


def inventory(roots: list[Path]) -> tuple[list[Path], list[str]]:
    """Знаходить лише run_*.json без рекурсії та явно діагностує повторні шляхи."""
    paths, warnings = set(), []
    seen = set()
    for root in roots:
        root = root.resolve()
        if root in seen:
            warnings.append(f'Повторний каталог пропущено: {root}')
            continue
        seen.add(root)
        if not root.is_dir():
            raise EvaluationError(f'Не існує каталогу runs: {root}')
        runs = {p.resolve() for p in root.glob('run_*.json') if p.is_file()}
        if not runs:
            raise EvaluationError(f'Немає run_*.json у {root}')
        warnings.append(f'{root}: ігноровано інших файлів: '
                        f'{sum(p.is_file() for p in root.iterdir()) - len(runs)}')
        paths.update(runs)
    return sorted(paths), warnings


def preflight_output(output: Path, roots: list[Path], protected: list[Path]) -> None:
    """Забороняє перетин output/inputs і мовчазний перезапис готових звітів."""
    output = output.resolve()
    for root in roots:
        root = root.resolve()
        if output == root or output in root.parents or root in output.parents:
            raise EvaluationError('Output не може перетинатися з каталогами runs.')
    for path in protected:
        if output == path.resolve() or output in path.resolve().parents:
            raise EvaluationError('Output містить захищені вхідні файли.')
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise EvaluationError('Output повинен бути новим або порожнім каталогом.')


def load_dataset(golden_path: Path, roots: list[Path], manifest_path: Path,
                 rules_path: Path, strict: bool = False) -> Dataset:
    """Будує групи конфігурацій і provenance, не змінюючи входів або їхніх міток."""
    golden, provisional = load_golden(golden_path, strict)
    rows = read_json(manifest_path)
    if not isinstance(rows, list) or any(not isinstance(m, dict) or 'id' not in m for m in rows):
        raise EvaluationError('Некоректний manifest.')
    manifest = {m['id']: m for m in rows}
    if len(manifest) != len(rows):
        raise EvaluationError('Повторні ID у manifest.')
    paths, warnings = inventory(roots)
    groups = {}
    for path in paths:
        run = load_run(path)
        group = groups.setdefault(run.group_id, [])
        if any(r.document_id == run.document_id for r in group):
            previous = next(r.path for r in group if r.document_id == run.document_id)
            raise EvaluationError(f'Дублікат {run.document_id}: {previous}; {path}')
        group.append(run)
    for group in groups.values():
        group.sort(key=lambda r: r.document_id)
    conflicts, source_hashes = _source_context(manifest, manifest_path.parent, warnings)
    files = [golden_path, manifest_path, rules_path, *paths]
    provenance = {'evaluator_version': __version__, 'policy_version': policy.POLICY_VERSION,
                  'policy_sha256': digest(Path(policy.__file__)), 'python': platform.python_version(),
                  'pydantic': pydantic.__version__, 'inputs': {str(p.resolve()): digest(p) for p in files},
                  'sources': source_hashes}
    return Dataset(golden, dict(sorted(groups.items())), provenance, manifest, conflicts,
                   warnings, provisional)


def _source_context(manifest: dict, parent: Path, warnings: list) -> tuple[dict, dict]:
    """Перевіряє fingerprint джерела перед застосуванням відомої суперечності."""
    conflicts, hashes = {}, {}
    for doc, entry in manifest.items():
        if not isinstance(entry.get('text_path'), str):
            warnings.append(f'{doc}: немає text_path, перевірка джерела недоступна')
            continue
        path = (parent / entry['text_path']).resolve()
        if not path.is_file():
            warnings.append(f'{doc}: джерело недоступне для fingerprint')
            continue
        actual = digest(path)
        hashes[str(path)] = actual
        if entry.get('sha256') and entry['sha256'] != actual:
            warnings.append(f'{doc}: SHA-256 джерела не відповідає manifest')
        known = policy.SOURCE_CONFLICTS.get(doc)
        if known:
            conflicts[doc] = {**known, 'source_path': str(path),
                              'fingerprint_valid': actual == known['sha256']}
            if not conflicts[doc]['fingerprint_valid']:
                warnings.append(f'{doc}: registry source_conflict застарів')
    return conflicts, hashes
