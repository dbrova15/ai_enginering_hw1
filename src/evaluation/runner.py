"""Оркестрація офлайнового оцінювання: перевірені входи → метрики → звіти."""

from datetime import datetime, timezone
from pathlib import Path

from src.evaluation.loading import load_dataset, preflight_output
from src.evaluation.metrics import aggregate_quality, ratio, runtime_metrics
from src.evaluation.models import digest
from src.evaluation.policy import FORMAT_VERSION
from src.evaluation.reporting import write_reports
from src.evaluation.scoring import score_document
from src.evaluation.usage import load_pricing


def _documents(dataset, group_id: str, runs: list) -> list:
    """Повертає деталі для кожного golden ID, включно з відсутніми прогнозами."""
    by_id = {r.document_id: r for r in runs}
    documents = []
    for doc, gold in sorted(dataset.golden.items()):
        run = by_id.get(doc)
        conflict = dataset.source_conflicts.get(doc)
        active = conflict if conflict and conflict['fingerprint_valid'] else None
        fields = score_document(gold['expected'], run.result if run else None, active)
        for value in fields.values():
            for check in value['checks']:
                check['scoped_check_id'] = f"{group_id}/{doc}/{check['check_id']}"
        documents.append({'document_id': doc, 'annotation_status': gold['annotation_status'],
                          'run_path': str(run.path) if run else None,
                          'run_sha256': digest(run.path) if run else None,
                          'prediction_available': run is not None and run.result is not None,
                          'source_conflict': conflict, 'fields': fields})
    return documents


def _group_summary(dataset, group_id: str, runs: list, documents: list, pricing: list) -> dict:
    """Зводить одну точну конфігурацію без вибору найкращої спроби документа."""
    ids = {r.document_id for r in runs}
    golden_ids = set(dataset.golden)
    return {'group_id': group_id, 'config': runs[0].config, 'document_ids': sorted(ids),
            'golden_document_ids': sorted(golden_ids), 'missing_document_ids': sorted(golden_ids - ids),
            'non_golden_document_ids': sorted(ids - golden_ids),
            'coverage': ratio(len(ids & golden_ids), len(golden_ids), 'present golden runs/G', 'all golden IDs'),
            'runtime': runtime_metrics(runs, pricing), 'quality': aggregate_quality(documents)}


def evaluate(golden: Path, roots: list[Path], output: Path, manifest: Path,
             rules: Path, strict: bool = False, pricing_path: Path | None = None) -> tuple[dict, int]:
    """Виконує повний локальний експеримент оцінювання та повертає summary/exit code.

    Не викликає моделі. Перед записом перевіряє перетин шляхів і незмінність
    усіх fingerprint входів, тому не видає змішані під час запуску дані за один snapshot.
    """
    protected = [golden, manifest, rules] + ([pricing_path] if pricing_path else [])
    preflight_output(output, roots, protected)
    dataset = load_dataset(golden, roots, manifest, rules, strict)
    pricing = load_pricing(pricing_path)
    preflight_output(output, roots, protected + [Path(p) for p in dataset.provenance['sources']])
    if pricing_path:
        dataset.provenance['inputs'][str(pricing_path.resolve())] = digest(pricing_path)
    code = Path(__file__).parent
    dataset.provenance['implementation'] = {p.name: digest(p) for p in sorted(code.glob('*.py'))}
    groups, detailed_groups = [], []
    duplicate_labels = False
    for group_id, runs in dataset.groups.items():
        documents = _documents(dataset, group_id, runs)
        duplicate_labels |= any(f.get('duplicate_golden') for d in documents for f in d['fields'].values())
        groups.append(_group_summary(dataset, group_id, runs, documents, pricing))
        detailed_groups.append({'group_id': group_id, 'documents': documents})
    status = 'provisional' if dataset.provisional or duplicate_labels else 'approved_labels'
    common = {'format_version': FORMAT_VERSION, 'evaluation_status': status,
              'provenance': dataset.provenance}
    summary = {**common, 'generated_at': datetime.now(timezone.utc).isoformat(),
               'golden_documents': len(dataset.golden), 'groups': groups, 'warnings': dataset.warnings,
               'cli': {'golden': str(golden), 'runs': [str(p) for p in roots], 'output_dir': str(output),
                       'manifest': str(manifest), 'annotation_rules': str(rules),
                       'strict_golden': strict, 'pricing': str(pricing_path) if pricing_path else None}}
    details = {**common, 'groups': detailed_groups}
    _check_inputs(dataset.provenance)
    write_reports(output, summary, details)
    failed = any(g['missing_document_ids'] or g['runtime']['valid_final']['value'] != 1
                 or g['runtime']['problems'] for g in groups)
    return summary, int(failed)


def _check_inputs(provenance: dict) -> None:
    """Відхиляє запис, якщо вхідний snapshot змінився під час обчислення."""
    from src.evaluation.models import EvaluationError

    for path, expected in {**provenance['inputs'], **provenance['sources']}.items():
        if digest(Path(path)) != expected:
            raise EvaluationError(f'Вхід змінився під час оцінювання: {path}')
