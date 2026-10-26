"""Офлайнове оцінювання Schema v2 з незмінним знаменником golden set."""

from pathlib import Path

from src.evaluation.loading import preflight_output
from src.evaluation.models import EvaluationError, digest
from src.evaluation.runtime import ratio, runtime_metrics
from src.evaluation.usage import load_pricing
from src.evaluation_v2 import POLICY_VERSION
from src.evaluation_v2.loading import load_golden, load_runs
from src.evaluation_v2.reporting import write_reports
from src.evaluation_v2.scoring import aggregate, score
from src.schemas import SCHEMA_V2


def evaluate(golden_path: Path, roots: list[Path], output: Path, manifest: Path,
             rules: Path, strict: bool = False, pricing_path: Path | None = None) -> tuple[dict, int]:
    """Читає лише збережені файли, перевіряє походження й формує три нові звіти.

    Відсутній або невалідний прогноз отримує нуль правильних полів, але його
    еталон залишається у знаменнику. Provisional не є ручним затвердженням.
    Повертає код 1 для неповного coverage, 0 для технічно повного набору;
    помилки контракту переривають оцінювання до запису звітів.
    """
    protected = [golden_path, manifest, rules]
    if pricing_path:
        protected.append(pricing_path)
    preflight_output(output, roots, protected)
    golden, provisional = load_golden(golden_path, strict)
    groups, plans, hashes, warnings = load_runs(roots, manifest)
    pricing = load_pricing(pricing_path)
    hashes.update({str(p.resolve()): digest(p) for p in (golden_path, manifest, rules)})
    implementation = [*Path(__file__).parent.glob('*.py'),
                      Path(__file__).parents[1] / 'evaluation/runtime.py',
                      Path(__file__).parents[1] / 'evaluation/usage.py',
                      Path(__file__).parents[1] / 'evaluation/loading.py',
                      *Path(__file__).parents[1].joinpath('schemas').glob('*.py')]
    input_hashes, summaries, details = {}, [], []
    incomplete = False
    for group_id, runs in sorted(groups.items()):
        for run in runs:
            pair = (run.data['source_sha256'], run.data['input_text_sha256'])
            if run.document_id in input_hashes and input_hashes[run.document_id] != pair:
                raise EvaluationError('Різні prepared inputs не можна порівнювати як один експеримент.')
            input_hashes[run.document_id] = pair
        summary, detail = evaluate_group(group_id, runs, plans[group_id], golden, pricing)
        incomplete |= bool(summary['coverage']['missing_primary_ids'] or summary['coverage']['missing_golden_ids'])
        summaries.append(summary)
        details.append(detail)
    summary = {'schema_version': 'v2', 'schema_sha256': SCHEMA_V2.sha256,
               'evaluator_policy_version': POLICY_VERSION,
               'evaluation_status': 'partial' if incomplete else 'completed',
               'annotation_status': 'provisional' if provisional else 'approved',
               'golden_documents': len(golden), 'golden_sha256': digest(golden_path),
               'implementation_sha256': {str(p.resolve()): digest(p) for p in sorted(implementation)},
               'input_hashes': input_hashes, 'file_sha256': hashes,
               'warnings': sorted(set(warnings)), 'groups': summaries}
    write_reports(output, summary, {'schema_version': 'v2', 'groups': details})
    return summary, int(incomplete)


def evaluate_group(group_id: str, runs: list, plan: dict, golden: dict, pricing: list) -> tuple[dict, dict]:
    """Розділяє G еталонів і N запланованих запусків; latency не отримує вигаданих нулів."""
    by_id = {run.document_id: run for run in runs}
    documents = []
    for doc, row in sorted(golden.items()):
        run = by_id.get(doc)
        documents.append({'document_id': doc, 'run_path': str(run.path) if run else None,
                          'status': run.data['status'] if run else 'missing',
                          'fields': score(row['expected'], run.result if run else None)})
    golden_runs = [r for r in runs if r.document_id in golden]
    runtime = runtime_metrics(golden_runs, pricing)
    runtime['basis'] = 'golden_10' if len(golden) == 10 else 'all golden IDs'
    runtime['valid_over_golden'] = ratio(sum(r.result is not None for r in golden_runs), len(golden),
                                        'V_G/G', runtime['basis'])
    runtime['missing_documents'] = len(golden) - len(golden_runs)
    missing = sorted(set(plan['planned_ids']) - by_id.keys())
    summary = {'group_id': group_id, 'configuration': runs[0].config,
               'experiment_status': 'partial' if missing else 'completed',
               'coverage': {'planned_primary': len(plan['planned_ids']), 'received_primary': len(runs),
                            'missing_primary_ids': missing, 'golden_documents': len(golden),
                            'received_golden': len(golden_runs),
                            'missing_golden_ids': sorted(set(golden) - by_id.keys())},
               'quality': aggregate(documents), 'runtime': runtime}
    if len(plan['planned_ids']) == 30:
        summary['baseline_all_30'] = {'basis': 'all_30', **runtime_metrics(runs, pricing)}
    return summary, {'group_id': group_id, 'documents': documents}
