"""Підготовка TXT-документів і послідовне витягування зі збереженням звітів."""

import hashlib
import json
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
from src.schemas import SCHEMA_V1, SchemaSpec

TEXT_PREPARATION_VERSION = 'schema-v2-text-v1'


def prepare_article_text(original: str) -> str:
    """Готує v2 input без зміни TXT чи видалення змістових згадок.

    Після заголовка розпізнає тільки повний початковий блок Автори/Категорії/
    Плати у визначеному порядку. Поза цим блоком, у цитатах і коді однакові
    слова зберігаються. Порожні рядки збережені, переноси уніфіковані до LF.
    """
    normalized = original.replace('\r\n', '\n').replace('\r', '\n')
    lines = normalized.splitlines(keepends=True)
    content = [i for i, line in enumerate(lines) if line.strip()]
    if len(content) < 4:
        return normalized
    header = content[1:4]
    labels = ('Автори:', 'Категорії:', 'Плати:')
    if all(lines[index].startswith(label) and lines[index][len(label):].strip()
           for index, label in zip(header, labels)):
        return ''.join(line for i, line in enumerate(lines) if i not in header)
    return normalized


def select_document_ids(path: Path, texts_root: Path) -> list['PreparedDocument']:
    """Читає лише ID, не expected labels, і перевіряє всі вибрані файли до API.

    Порожні/повторні/невідомі ID та однаковий ID у різних файлах відхиляються.
    Функція повертає тільки потрібні документи у відтворюваному порядку.
    """
    ids = read_nonempty(path).splitlines()
    if any(not item.strip() for item in ids) or len(ids) != len(set(ids)):
        raise InputFileError('ID-файл містить порожні або повторні ID.')
    manifest_path = texts_root.parent / 'manifest.json'
    if manifest_path.is_file():
        known = {row['id'] for row in json.loads(manifest_path.read_text(encoding='utf-8'))}
        if set(ids) - known:
            raise InputFileError('ID відсутній у manifest.')
    documents = []
    for doc in sorted(ids):
        matches = [p for p in texts_root.rglob('*') if p.is_file() and
                   p.suffix.lower() == '.txt' and p.stem == doc]
        if len(matches) != 1:
            raise InputFileError('Кожен ID повинен однозначно визначати існуючий TXT.')
        documents.append(PreparedDocument(matches[0], read_nonempty(matches[0])))
    return documents


def guard_v2_output(output: Path, project_root: Path) -> None:
    """Дозволяє тільки новий/порожній v2 output, захищає історичні results.

    Не змінює каталогів і викликається до HTTP. Стандартна v2-гілка результатів
    schema_v2 не перетинається з історичними step/evaluation-каталогами.
    """
    target, results = output.resolve(), (project_root / 'results').resolve()
    protected = [results / 'step1', results / 'step2', *results.glob('evaluation*'),
                 project_root / 'data', project_root / 'src', project_root / 'prompts']
    if target == results or target == project_root.resolve() or any(
        target == p.resolve() or target in p.resolve().parents or p.resolve() in target.parents
        for p in protected):
        raise InputFileError('V2 output не може перетинатися з вихідними/історичними даними.')
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise InputFileError('V2 output має бути новим або порожнім каталогом.')


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
    *, schema_spec: SchemaSpec = SCHEMA_V1, run_kind: str = 'primary',
) -> tuple[dict[str, Any], Path]:
    """Обробляє одну підготовлену статтю й записує звіт попереднього формату.

    Створює окремий HTTP-клієнт, викликає спільний конвеєр із retry/repair,
    додає метадані та зберігає новий UUID-файл. Повертає звіт і його шлях.
    Latency, як раніше, включає створення клієнта та витягування, але не запис
    файла. Помилка запису передається main; попередні результати не перезаписуються.
    """
    if run_kind not in ('primary', 'probe', 'warmup'):
        raise InputFileError('Невідомий kind запуску.')
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    with httpx.Client() as http_client:
        client = (create_client(settings, http_client) if schema_spec.version == 'v1' else
                  create_client(settings, http_client, schema_spec=schema_spec))
        article = document.text if schema_spec.version == 'v1' else prepare_article_text(document.text)
        extracted = extract_document(client, prompt, article)
    result = {
        'document_id': document.path.stem,
        'source_path': str(document.path.resolve()), 'schema_version': schema_spec.version,
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
    if schema_spec.version == 'v2':
        result.update(schema_sha256=schema_spec.sha256, experiment_id=output_dir.resolve().name,
                      source_sha256=hashlib.sha256(document.text.encode('utf-8')).hexdigest(),
                      input_text_sha256=hashlib.sha256(article.encode('utf-8')).hexdigest(),
                      text_preparation_version=TEXT_PREPARATION_VERSION, kind=run_kind,
                      output_mode='chat_completions.json_schema.strict')
        result['prompt']['namespace'] = 'schema_v2'
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
    *, schema_spec: SchemaSpec = SCHEMA_V1,
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
        result, path = (run_document(settings, document, prompt, prompt_path, output_dir)
                        if schema_spec.version == 'v1' else run_document(
                            settings, document, prompt, prompt_path, output_dir, schema_spec=schema_spec))
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
    if schema_spec.version == 'v2':
        manifest = {'schema_version': 'v2', 'experiment_id': output_dir.resolve().name,
                    'planned_ids': [d.path.stem for d in documents], 'planned_count': summary.total,
                    'processed_count': summary.total - summary.not_processed,
                    'status': 'partial' if summary.not_processed else 'completed',
                    'provider': settings.provider, 'model': settings.model,
                    'sampling': {'temperature': settings.temperature, 'top_p': settings.top_p},
                    'prompt_namespace': 'schema_v2', 'prompt_version': prompt_path.stem,
                    'prompt_sha256': hashlib.sha256(prompt.encode('utf-8')).hexdigest(),
                    'schema_sha256': schema_spec.sha256}
        with (output_dir / 'experiment_manifest.json').open('x', encoding='utf-8') as stream:
            json.dump(manifest, stream, ensure_ascii=False, indent=2)
    return summary
