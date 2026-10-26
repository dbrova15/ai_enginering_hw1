"""Офлайнове точне оцінювання enum/bool/list для Schema v2."""

import argparse
import sys
from pathlib import Path

from src.evaluation.models import EvaluationError
from src.evaluation_v2.runner import evaluate

ROOT = Path(__file__).resolve().parent


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Отримує шляхи й strict/provisional режим; API та .env не використовуються."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--golden', type=Path, required=True)
    parser.add_argument('--runs', type=Path, nargs='+', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'data/sourses/hm1/manifest.json')
    parser.add_argument('--annotation-rules', type=Path, default=ROOT / 'data/golden_annotation_rules_v2.md')
    parser.add_argument('--pricing', type=Path)
    parser.add_argument('--strict-golden', action='store_true')
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Повертає 0 для повного coverage, 1 для partial, 2 для помилки входів/запису.

    Технічна повнота не означає правильність прогнозів або ручне затвердження
    еталонів: annotation_status друкується окремо й збережений у summary.
    """
    args = parse_args(argv)
    try:
        summary, code = evaluate(args.golden, args.runs, args.output_dir, args.manifest,
                                 args.annotation_rules, args.strict_golden, args.pricing)
    except (EvaluationError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f'Помилка оцінювання v2: {exc}', file=sys.stderr)
        return 2
    print(f"Schema v2: {summary['evaluation_status']}; golden: {summary['annotation_status']}; {args.output_dir}")
    return code


if __name__ == '__main__':
    raise SystemExit(main())
