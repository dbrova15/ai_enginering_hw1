"""Офлайнове порівняння версій evaluator на однакових документах і контрольних фактах."""

import argparse
import sys
from pathlib import Path

from src.evaluation.comparison import compare
from src.evaluation.models import EvaluationError


def main(argv: list[str] | None = None) -> int:
    """Читає чотири snapshots, перевіряє порівнюваність і записує до/після без overwrite."""
    parser = argparse.ArgumentParser(description='Порівняти evaluator policies без запуску LLM.')
    for key in ('before', 'after', 'controls-before', 'controls-after', 'output-dir'):
        parser.add_argument('--' + key, type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = compare(args.before, args.after, args.controls_before, args.controls_after, args.output_dir)
    except (EvaluationError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f'Помилка порівняння: {type(exc).__name__}', file=sys.stderr)
        return 2
    print(f"Порівняння збережено: {args.output_dir}; corrected control FN: {len(result['controls']['fixed_fn_ids'])}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
