"""Витягування даних через обраний у .env API: python main.py --help."""

import argparse
import sys
from pathlib import Path

from src.config import PROJECT_ROOT, ConfigError, load_settings
from src.document_runner import InputFileError, prepare_documents, read_nonempty, run_documents


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
    parser.add_argument('--prompt', type=Path, default=PROJECT_ROOT / 'prompts/v1.txt',
                        help='Шлях до системного промпту; типово prompts/v1.txt.')
    parser.add_argument('--output-dir', type=Path, default=PROJECT_ROOT / 'results',
                        help='Каталог нових JSON-звітів; типово results/.')
    return parser.parse_args(argv)


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
        prompt = read_nonempty(args.prompt)
        documents = prepare_documents(args.document, args.all_documents, TEXTS_ROOT)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        summary = run_documents(settings, documents, prompt, args.prompt,
                                args.output_dir, show_progress=args.all_documents)
    except (ConfigError, OSError, UnicodeError, ValueError) as exc:
        # Текст стороннього винятку може містити секрет, тому показуємо лише безпечні пояснення.
        message = str(exc) if isinstance(exc, (ConfigError, InputFileError)) else 'Перевірте шляхи, UTF-8, вміст файлів і доступ до каталогу результатів.'
        print(f'Помилка: {message}', file=sys.stderr)
        return 2
    return 1 if summary.failed or summary.not_processed else 0


if __name__ == '__main__':
    raise SystemExit(main())
