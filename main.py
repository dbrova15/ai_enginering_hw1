"""Витягування даних через обраний у .env API: python main.py --help."""

import argparse
import sys
import uuid
from pathlib import Path

from src.config import PROJECT_ROOT, ConfigError, load_settings
from src.document_runner import InputFileError, prepare_documents, read_nonempty, run_documents
from src.document_runner import guard_v2_output, select_document_ids
from src.config import Settings
from src.schemas import get_schema


TEXTS_ROOT = PROJECT_ROOT / 'data/sourses/hm1/texts'


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Читає аргументи командного рядка та повертає вибрані шляхи.

    Дозволяє вибрати один документ або всі TXT корпусу, промпт і каталог звітів.
    Без аргументів використовує коротку статтю HR-0187 та baseline v1.
    --help показує підказку без API-запиту; невідомі аргументи зупиняють запуск.
    argv потрібен для офлайнової перевірки CLI; зазвичай береться командний рядок.
    """
    parser = argparse.ArgumentParser(description='Витягування з одного TXT або всього корпусу; провайдер визначається LLM_PROVIDER.')
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--document', type=Path,
                           default=TEXTS_ROOT / 'uk/HR-0187.txt',
                           help='Шлях до однієї TXT-статті; типово HR-0187 про автополив.')
    selection.add_argument('--all-documents', action='store_true',
                           help='Послідовно обробити всі TXT у data/sourses/hm1/texts та підкаталогах.')
    selection.add_argument('--document-ids', type=Path, help='UTF-8-файл унікальних document_id, по одному на рядок.')
    parser.add_argument('--schema-version', choices=('v1', 'v2'), default='v1')
    parser.add_argument('--temperature', type=float, default=None)
    parser.add_argument('--top-p', type=float, default=None)
    parser.add_argument('--prompt', type=Path, default=None,
                        help='Шлях до системного промпту; типово prompts/v1.txt.')
    parser.add_argument('--output-dir', type=Path, default=None,
                        help='Каталог нових JSON-звітів; типово results/.')
    args = parser.parse_args(argv)
    if args.prompt is None:
        args.prompt = PROJECT_ROOT / ('prompts/v1.txt' if args.schema_version == 'v1' else 'prompts/schema_v2/v1.txt')
    if args.output_dir is None:
        args.output_dir = PROJECT_ROOT / 'results'
        if args.schema_version == 'v2':
            args.output_dir = args.output_dir / 'schema_v2/baseline' / uuid.uuid4().hex
    return args


def main(argv: list[str] | None = None) -> int:
    """Координує одиночний або пакетний запуск і повертає код завершення.

    Спочатку перевіряє налаштування й файли, потім викликає модель, додає
    звіти в окремих файлах. Пакетний режим перевіряє весь набір до першого
    запиту. Для всіх успішних/виправлених відповідей повертає 0, за наявності
    failed чи необробленої решти — 1, для локальної помилки — 2. Ключ не друкує.
    Реальний запуск із налаштованим ключем і моделлю може витрачати API-кредити.
    """
    args = parse_args(argv)
    try:
        settings = load_settings()
        changes = {k: v for k, v in {'temperature': args.temperature, 'top_p': args.top_p}.items() if v is not None}
        if changes:
            settings = Settings.model_validate({**settings.model_dump(), **changes})
        schema_spec = get_schema(args.schema_version)
        prompt = read_nonempty(args.prompt)
        documents = (select_document_ids(args.document_ids, TEXTS_ROOT) if args.document_ids else
                     prepare_documents(args.document, args.all_documents, TEXTS_ROOT))
        if args.document_ids and len(documents) != 10:
            raise InputFileError('--document-ids потребує рівно 10 унікальних ID.')
        if schema_spec.version == 'v2':
            guard_v2_output(args.output_dir, PROJECT_ROOT)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        options = {'schema_spec': schema_spec} if schema_spec.version == 'v2' else {}
        summary = run_documents(settings, documents, prompt, args.prompt, args.output_dir,
                                show_progress=args.all_documents or bool(args.document_ids), **options)
    except (ConfigError, OSError, UnicodeError, ValueError) as exc:
        # Текст стороннього винятку може містити секрет, тому показуємо лише безпечні пояснення.
        message = str(exc) if isinstance(exc, (ConfigError, InputFileError)) else 'Перевірте шляхи, UTF-8, вміст файлів і доступ до каталогу результатів.'
        print(f'Помилка: {message}', file=sys.stderr)
        return 2
    return 1 if summary.failed or summary.not_processed else 0


if __name__ == '__main__':
    raise SystemExit(main())
