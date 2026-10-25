"""Збереження окремого JSON-звіту запуску без перезапису й витоку API-ключа."""

import json
from pathlib import Path
from typing import Any
from uuid import uuid4


def redact_secret(value: Any, secret: str) -> Any:
    """Повертає копію вкладених даних із замаскованим API-ключем.

    Переглядає рядки, списки та словники, включно з назвами ключів. Це захищає
    журнал навіть тоді, коли сервер випадково віддзеркалив секрет у відповіді.
    Початкові дані не змінює; для відсутнього секрету нічого не замінює.
    """
    if isinstance(value, str):
        return value.replace(secret, '[REDACTED]') if secret else value
    if isinstance(value, list):
        return [redact_secret(item, secret) for item in value]
    if isinstance(value, dict):
        return {redact_secret(key, secret): redact_secret(item, secret)
                for key, item in value.items()}
    return value


def save_result(result: dict[str, Any], output_dir: Path, secret: str) -> Path:
    """Записує звіт у новий UTF-8 JSON-файл і повертає його шлях.

    Отримує готові дані, каталог і ключ для маскування. Створює каталог за
    потреби, генерує унікальне ім'я й відкриває файл у режимі без перезапису.
    Старі результати зберігаються. Помилки доступу до диска передаються
    викликачеві, щоб програма не повідомила про збереження, якого не сталося.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f'run_{uuid4().hex}.json'
    safe = redact_secret(result, secret)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(safe, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    return path
