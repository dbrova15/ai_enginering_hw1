"""Підготовка TXT-документів і послідовне витягування зі збереженням звітів."""

import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from src.client_factory import create_client
from src.config import Settings
from src.extraction import extract_document
from src.result_writer import save_result


class InputFileError(ValueError):
    """Безпечне пояснення неправильного вхідного файла або каталогу.

    Відрізняє помилки вибору документа від помилок API. main показує цей
    текст без traceback; повідомлення не містять вмісту статті чи API-ключів.
    """


@dataclass
class PreparedDocument:
    """Один документ, перевірений і прочитаний до початку API-запитів.

    path зберігає шлях для ID та метаданих, text — вміст однієї статті.
    Об'єкт не виконує запитів; тексти різних документів не об'єднуються в промпті.
    """

    path: Path
    text: str


@dataclass
class RunSummary:
    """Лічильники поточного запуску без вигаданих метрик якості.

    total — кількість підготовлених документів. success і repaired рахуються
    окремо, failed означає завершені невдалі спроби. При достроковій зупинці
    решта документів залишаються необробленими й не зараховуються до failed.
    """

    total: int
    success: int = 0
    repaired: int = 0
    failed: int = 0

    @property
    def not_processed(self) -> int:
        """Повертає кількість документів, до яких черга ще не дійшла.

        Обчислює різницю між total та трьома лічильниками завершених спроб.
        Не звертається до результатів попередніх запусків і нічого не змінює.
        """
        return self.total - self.success - self.repaired - self.failed


def read_nonempty(path: Path) -> str:
    """Читає один непорожній UTF-8-файл зі збереженням переносів рядків.

    Повертає весь текст, щоб хеш промпту відповідав його байтам. Каталог,
    відсутній файл, порожній текст або інше кодування спричиняють InputFileError
    із поясненням без показу вмісту. Файлів не змінює й API не викликає.
    """
    if path.is_dir():
        raise InputFileError('Очікується файл, а не каталог. Для всіх статей використайте --all-documents.')
    if not path.is_file():
        raise InputFileError('Вхідний файл не існує. Перевірте шлях у --document або --prompt.')
    try:
        text = path.read_bytes().decode('utf-8')
    except UnicodeError:
        raise InputFileError('Вхідний файл має бути текстом у кодуванні UTF-8.') from None
    if not text.strip():
        raise InputFileError('Вхідний файл порожній. Перевірте документ і промпт.')
    return text


def prepare_documents(document: Path, all_documents: bool, texts_root: Path) -> list[PreparedDocument]:
    """Визначає файли та читає всі вхідні статті до першого API-запиту.

    У звичайному режимі бере document. Для all_documents рекурсивно знаходить
    TXT у texts_root, сортує шляхи для відтворюваного порядку та читає кожен
    окремо. Порожній/відсутній каталог або неправильний файл зупиняють запуск
    через InputFileError. Функція не викликає модель і не перевіряє старі звіти.
    """
    if not all_documents:
        return [PreparedDocument(document, read_nonempty(document))]
    if not texts_root.is_dir():
        raise InputFileError('Каталог data/sourses/hm1/texts відсутній або не є каталогом.')
    paths = sorted((path for path in texts_root.rglob('*')
                    if path.is_file() and path.suffix.lower() == '.txt'),
                   key=lambda path: path.relative_to(texts_root).as_posix())
    if not paths:
        raise InputFileError('У каталозі data/sourses/hm1/texts немає TXT-документів.')
    return [PreparedDocument(path, read_nonempty(path)) for path in paths]


def run_document(
    settings: Settings, document: PreparedDocument, prompt: str,
    prompt_path: Path, output_dir: Path,
) -> tuple[dict[str, Any], Path]:
    """Обробляє одну підготовлену статтю й записує звіт попереднього формату.

    Створює окремий HTTP-клієнт, викликає спільний конвеєр із retry/repair,
    додає метадані та зберігає новий UUID-файл. Повертає звіт і його шлях.
    Latency, як раніше, включає створення клієнта та витягування, але не запис
    файла. Помилка запису передається main; попередні результати не перезаписуються.
    """
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    with httpx.Client() as http_client:
        client = create_client(settings, http_client)
        extracted = extract_document(client, prompt, document.text)
    result = {
        'document_id': document.path.stem,
        'source_path': str(document.path.resolve()), 'schema_version': 'v1',
        'provider': settings.provider, 'requested_model': settings.model,
        'prompt': {'version': prompt_path.stem,
                   'sha256': hashlib.sha256(prompt.encode('utf-8')).hexdigest()},
        'sampling': {'temperature': settings.temperature, 'top_p': settings.top_p},
        'limits': {'timeout_seconds': settings.timeout_seconds,
                   'max_retries': settings.max_retries, 'max_tokens': settings.max_tokens,
                   'retry_base_seconds': settings.retry_base_seconds,
                   'max_retry_wait_seconds': settings.max_retry_wait_seconds},
        'started_at_utc': started_at,
        'latency_seconds': time.perf_counter() - started,
        **extracted,
    }
    path = save_result(result, output_dir, settings.api_key.get_secret_value())
    return result, path


def service_unavailable(result: dict[str, Any]) -> bool:
    """Визначає, чи треба зупинити чергу через збій сервісу або доступу.

    Перевіряє останню HTTP-спробу останньої генерації. 401/402/403/404/408/429,
    5xx або мережевий збій після вичерпання retry означають, що продовжувати
    чергу зараз недоцільно. Помилка JSON/схеми чи HTTP 400 окремого документа
    дозволяє перейти до наступного. Сам результат і попередні файли не змінює.
    """
    if result['status'] != 'failed':
        return False
    status = result['attempts'][-1]['requests'][-1]['http_status']
    return status is None or status in (401, 402, 403, 404, 408, 429) or status >= 500


def run_documents(
    settings: Settings, documents: list[PreparedDocument], prompt: str,
    prompt_path: Path, output_dir: Path, show_progress: bool = False,
) -> RunSummary:
    """Послідовно обробляє підготовлені документи та повертає лічильники запуску.

    Для кожної статті викликає run_document і друкує шлях окремого звіту.
    У пакетному режимі додає прогрес і фінальний підсумок. Failed окремого
    документа не заважає наступному, але недоступний сервіс зупиняє чергу;
    необроблена решта показується окремо. Старі звіти не використовуються для
    пропуску статей: кожен запуск навмисно створює новий набір відповідей.
    """
    summary = RunSummary(total=len(documents))
    for index, document in enumerate(documents, 1):
        if show_progress:
            print(f'[{index}/{summary.total}] {document.path.name}', flush=True)
        result, path = run_document(settings, document, prompt, prompt_path, output_dir)
        if result['status'] == 'success':
            summary.success += 1
        elif result['status'] == 'repaired':
            summary.repaired += 1
        else:
            summary.failed += 1
        print(f"Статус: {result['status']}. Звіт збережено: {path}", flush=True)
        if service_unavailable(result):
            if show_progress:
                print('Чергу зупинено через помилку доступу, ліміт або недоступність сервісу.')
            break
    if show_progress:
        print(f'Підсумок: всього={summary.total}, success={summary.success}, '
              f'repaired={summary.repaired}, failed={summary.failed}, '
              f'не оброблено={summary.not_processed}.')
    return summary
