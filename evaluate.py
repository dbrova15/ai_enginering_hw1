"""Офлайнова оцінка збережених витягувань: python evaluate.py --help."""

import argparse
import sys
from pathlib import Path

from src.evaluation.models import EvaluationError
from src.evaluation.runner import evaluate

PROJECT_ROOT = Path(__file__).resolve().parent


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Читає шляхи та режим; help не читає .env і не викликає жодної моделі."""
    parser = argparse.ArgumentParser(description='Офлайнове порівняння runs із Golden Set.')
    parser.add_argument('--golden', type=Path, required=True)
    parser.add_argument('--runs', type=Path, nargs='+', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, default=PROJECT_ROOT / 'data/sourses/hm1/manifest.json')
    parser.add_argument('--annotation-rules', type=Path, default=PROJECT_ROOT / 'data/golden_annotation_rules_v1.md')
    parser.add_argument('--strict-golden', action='store_true', help='Дозволити лише annotation_status=approved.')
    parser.add_argument('--pricing', type=Path, help='Локальний JSON тарифів із датою та джерелом; без пошуку в мережі.')
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Створює три звіти, друкує статус і повертає 0/1/2 відповідно до повноти.

    0 означає технічно повний прогін, не гарантію точності моделі. 1 означає
    проблеми coverage/результатів із готовим звітом; 2 — фатальну помилку входів.
    """
    args = parse_args(argv)
    try:
        summary, code = evaluate(args.golden, args.runs, args.output_dir, args.manifest,
                                 args.annotation_rules, args.strict_golden, args.pricing)
    except EvaluationError as exc:
        print(f'Помилка оцінювання: {exc}', file=sys.stderr)
        return 2
    except (OSError, UnicodeError, ValueError, TypeError):
        print('Помилка оцінювання: перевірте доступ, формат і типи вхідних файлів.', file=sys.stderr)
        return 2
    print(f"Evaluation status: {summary['evaluation_status']}; груп: {len(summary['groups'])}; "
          f"golden: {summary['golden_documents']}; звіти: {args.output_dir}")
    return code


if __name__ == '__main__':
    raise SystemExit(main())
