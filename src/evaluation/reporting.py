"""Побудова JSON/Markdown та запис звітів без зміни вихідних експериментів."""

import json
import os
from pathlib import Path

from src.evaluation.models import EvaluationError
from src.evaluation.policy import PROVISIONAL_BANNER
from src.evaluation.scoring import FIELDS


def _display(value, percentage: bool = False) -> str:
    """Форматує вимір для таблиці; unknown не відображає як нуль."""
    if value is None:
        return 'невідомо'
    return f'{value:.1%}' if percentage else f'{value:.3f}'


def _cell(value) -> str:
    """Екранує дані для Markdown, щоб текст моделі не зламав таблицю."""
    return str(value).replace('|', '\\|').replace('\n', ' ').replace('\r', ' ')


def _link(path: str, output: Path) -> str:
    """Робить посилання переносним відносно каталогу звіту, якщо це можливо."""
    try:
        return Path(os.path.relpath(path, output.resolve())).as_posix().replace(' ', '%20')
    except ValueError:
        return Path(path).as_uri()


def render_markdown(summary: dict, details: dict, output: Path) -> str:
    """Збирає відтворювані таблиці та обмежені доказами висновки українською."""
    lines = ['# Порівняння Structured Extraction', '',
             PROVISIONAL_BANNER if summary['evaluation_status'] == 'provisional' else 'Evaluation status: approved labels', '',
             'Метрики вимірюють відповідність еталону за однією політикою, а не доведену фактичну істину.', '',
             '## Вибірка та конфігурації', '',
             f"Golden set: {summary['golden_documents']} документів. Усі golden ID входять у знаменники якості.", '',
             '| Група | Маршрут | Модель / snapshot | Prompt / hash | Sampling | Coverage |',
             '| --- | --- | --- | --- | --- | --- |']
    for group in summary['groups']:
        c = group['config']
        lines.append(f"| {group['group_id'][:8]} | {_cell(c['provider'])} | {_cell(c['requested_model'])} / "
                     f"{_cell(c['returned_model'])} | {_cell(c['prompt']['version'])} / {c['prompt']['sha256']} | "
                     f"{_cell(json.dumps(c['sampling'], sort_keys=True))} | {group['coverage']['numerator']}/{group['coverage']['denominator']} |")
    lines += ['', 'Різні маршрути API не обов’язково означають різні моделі. Різні snapshot, limits або sampling '
              'залишаються окремими конфігураціями. Повні параметри й хеші входів — у summary.json.', '',
              '## Виміряні метрики', '',
              '| Група | Valid first (confirmed / A) | Valid final | Failed / repaired | p50 / p95, с | Mean input / output | Cost/1000, USD |',
              '| --- | --- | --- | --- | --- | --- | --- |']
    for g in summary['groups']:
        r = g['runtime']; u = r['usage']; statuses = r['status_counts']
        lines.append(f"| {g['group_id'][:8]} | {_display(r['valid_first_confirmed']['value'], True)} | "
                     f"{_display(r['valid_final']['value'], True)} | {statuses.get('failed', 0)} / {statuses.get('repaired', 0)} | "
                     f"{_display(r['latency']['p50'])} / {_display(r['latency']['p95'])} | "
                     f"{_display(u['prompt_tokens']['mean_per_complete_document'])} / "
                     f"{_display(u['completion_tokens']['mean_per_complete_document'])} | "
                     f"{_display(u['cost']['cost_per_1000_documents'])} |")
    lines += ['', 'Час — latency конвеєра, включно зі збереженими retry/repair; квантилі: лінійна інтерполяція '
              '(n−1)q. Cold start не відокремлено: немає надійної позначки. Unknown не замінюється нулем. '
              'Usage включає кожен HTTP-запит один раз; mean рахується лише для повних документів. '
              'Cost/1000 — екстраполяція документів із повною вартістю, а не рахунок постачальника. '
              'Зовнішній тариф Ollama = 0; обладнання й електроенергія не оцінені. '
              'Known/unknown counts, знаменники, джерела цін та методи наведені в summary.json.', '',
              '### Точна відповідність восьми полів', '',
              '| Поле | ' + ' | '.join(g['group_id'][:8] for g in summary['groups']) + ' |',
              '| --- | ' + ' | '.join('---' for _ in summary['groups']) + ' |']
    for field in (*FIELDS, 'aggregate'):
        values = [g['quality']['aggregate_exact_accuracy'] if field == 'aggregate'
                  else g['quality']['field_exact_accuracy'][field] for g in summary['groups']]
        lines.append('| ' + field + ' | ' + ' | '.join(f"{v['numerator']}/{v['denominator']} ({_display(v['value'], True)})" for v in values) + ' |')
    lines += _list_tables(summary)
    lines += _fact_table(summary)
    lines += _examples(details, output)
    lines += _conclusions(summary)
    return '\n'.join(lines) + '\n'


def _fact_table(summary: dict) -> list[str]:
    """Відділяє фактні рішення від FP/FN, які також містять невизначені відповіді."""
    lines = ['', '### Підтверджені факти та обмеження зіставлення', '',
             '| Група | Поле | Match | Суперечності еталону | Review-пари | Ambiguous groups | Missing | Extra |',
             '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for group in summary['groups']:
        for field, counts in group['quality'].get('fact_assessment', {}).items():
            values = [counts[k] for k in ('confirmed_matches', 'confirmed_contradictions', 'needs_review_pairs',
                                         'ambiguous_groups', 'missing', 'extra_predicted')]
            lines.append(f"| {group['group_id'][:8]} | {field} | " + ' | '.join(map(str, values)) + ' |')
    lines += ['', 'Review-пари та неоднозначні групи не є доведеними помилками моделі й не дають TP. '
              'Суперечності встановлені відносно еталона за підтвердженої identity; це не зовнішня перевірка джерела. '
              'Непідтверджені model/manufacturer при golden null не називаються встановленою галюцинацією. '
              'Якщо subject невідомий, навіть різні числа означають лише умовну розбіжність. '
              'Missing/extra — незакриті факти; у review-групах це теж можуть бути потенційні відповідності. '
              'Категорії не є єдиною розбивкою: unsupported атрибут і review іншого атрибута можуть співіснувати.']
    return lines


def _list_tables(summary: dict) -> list[str]:
    """Показує PR/F1 окремо від exact accuracy та навантаження ручної перевірки."""
    lines = ['', '### Списки: micro-метрики', '',
             '| Група | Поле / режим | TP / FP / FN | Precision | Recall | F1 |',
             '| --- | --- | --- | --- | --- | --- |']
    for g in summary['groups']:
        for field, modes in g['quality']['lists'].items():
            for mode, values in modes.items():
                lines.append(f"| {g['group_id'][:8]} | {field} / {mode} | {values['tp']} / {values['fp']} / {values['fn']} | "
                             + ' | '.join(_display(values[k]['value'], True) for k in ('precision', 'recall', 'f1')) + ' |')
    lines += ['', 'P=TP/(TP+FP), R=TP/(TP+FN), F1=2TP/(2TP+FP+FN). Повний факт потребує правильних атрибутів; '
              'identity компонента не підтверджує model/manufacturer/role. Невизначений повний факт не є TP, '
              'тобто залишається у консервативних FP/FN. Нульовий знаменник дає null. '
              'Порожнє поле може мати exact match, але не вигаданий PR=100%.', '',
              '### Ручний перегляд та покриття', '']
    for g in summary['groups']:
        review = g['quality']['review']
        lines += [f"- {g['group_id'][:8]}: автоматично оцінено {review['auto_decided_checks']} атомарних перевірок; "
                  f"needs_review {review['needs_review']['numerator']}/{review['total_checks']}; "
                  f"недоступних перевірок {review['unavailable_checks']}; "
                  f"неоднозначних pairing-груп {review['ambiguous_pairing_groups']}; "
                  f"документів на перегляд {review['documents']['numerator']}/{review['documents']['denominator']}. "
                  f"Missing IDs: {', '.join(g['missing_document_ids']) or 'немає'}. "
                  f"Приклади поза golden: {len(g['non_golden_document_ids'])}."]
    return lines


def _examples(details: dict, output: Path) -> list[str]:
    """Обирає до п’яти різних типів розбіжностей у стабільному порядку без LLM-судді."""
    lines = ['', '## Приклади розбіжностей із еталоном', '',
             'extra_predicted означає відсутність відповідності в еталоні; це не доказ галюцинації. '
             'Можлива помилка самого еталона. Оригінальні та canonical значення доступні в details.json.', '']
    by_group = []
    for group in details['groups']:
        examples = []
        for doc in group['documents']:
            selected = False
            for field in ('technical_parameters', 'components', 'interfaces_protocols', 'software_tools',
                          'document_type', 'primary_topic', 'main_subject', 'purpose'):
                item = doc['fields'][field]
                for c in item['checks']:
                    if c['verdict'] != 'match':
                        examples.append((group, doc, field, c))
                        selected = True
                        break
                if selected:
                    break
        by_group.append(examples)
    examples = [items[index] for index in range(max((len(v) for v in by_group), default=0))
                for items in by_group if index < len(items)]
    for group, doc, field, c in examples[:5]:
        source = f"[run]({_link(doc['run_path'], output)})" if doc['run_path'] else 'run відсутній'
        lines += [f"### {doc['document_id']} / {group['group_id'][:8]} / {field}", '',
                  f"{source}; `{c['verdict']}` / `{c['reason_code']}`.", '',
                  f"Expected: `{_cell(json.dumps(c['expected'], ensure_ascii=False))}`.", '',
                  f"Predicted: `{_cell(json.dumps(c['predicted'], ensure_ascii=False))}`.", '',
                  'Встановлено розбіжність за вказаним правилом; причина поведінки моделі не встановлена.', '']
    if not examples:
        lines += ['Розбіжностей за цією політикою не знайдено; це не зовнішня перевірка фактів.', '']
    return lines


def _conclusions(summary: dict) -> list[str]:
    """Відокремлює виміри від інтерпретацій і не оголошує необґрунтованого переможця."""
    lines = ['', '## Висновок та обмеження достовірності', '', '### Що об’єктивно встановлено', '']
    for g in summary['groups']:
        a = g['quality']['aggregate_exact_accuracy']
        lines += [f"- {g['group_id'][:8]}: coverage {g['coverage']['numerator']}/{g['coverage']['denominator']}; "
                  f"строгих збігів полів {a['numerator']}/{a['denominator']}. Це вимір відповідності поточному еталону."]
    lines += ['', '### Сильні сторони кожної моделі', '']
    for g in summary['groups']:
        fields = g['quality']['field_exact_accuracy']
        strongest = max(fields, key=lambda f: (fields[f]['numerator'], f))
        lines += [f"- {g['group_id'][:8]}: найбільше exact matches у полі {strongest}: "
                  f"{fields[strongest]['numerator']}/{fields[strongest]['denominator']}; "
                  'це відносна характеристика цієї вибірки, не доказ загальної переваги.']
    lines += ['', '### Слабкі сторони кожної моделі', '']
    for g in summary['groups']:
        facts = g['quality']['lists']['technical_parameters']['full_fact']
        lines += [f"- {g['group_id'][:8]}: повні технічні факти TP={facts['tp']}, FP={facts['fp']}, FN={facts['fn']}; "
                  'FP/FN містять і консервативно не підтверджені формулювання, а не лише доведені помилки моделі.']
    lines += ['', '### Що не вдалося встановити', '',
              'Нуль strict full_fact TP не доводить відсутності правильних фактів: matcher може не '
              'розпізнати предмет або перефразування без затвердженого alias. '
              'Еталони можуть бути незатвердженими; семантичні перефразування, переклади, невідомі aliases і '
              'контекст не підтверджуються нечітким пошуком. Cold start, фактичне контекстне вікно, обладнання, '
              'повна локальна вартість і статистична значущість не встановлені. Кількість компонентів не є '
              'кількістю незалежних документів. Причини розбіжностей можуть включати правила еталона, '
              'обмеження matcher і модель; гіпотеза про промпт потребує окремого експерименту.', '',
              '### Чи можна визначити кращу модель', '',
              'За наявними даними неможливо впевнено визначити кращу модель. Необхідно враховувати '
              'повноту, зайві факти, needs_review, затримку та вартість, а не лише один показник.', '',
              '### Рекомендації для подальших експериментів', '',
              'Підтвердити еталони людиною; переглянути needs_review; задокументувати спільні aliases; '
              'порівняти ще одну sampling-конфігурацію та v2 на тій самій вибірці й policy hash; '
              'виміряти cold start окремо. Оцінювач не виконував цих експериментів.', '',
              '## Діагностика входів', '']
    lines += [f'- {_cell(w)}' for w in summary['warnings']]
    return lines


def write_reports(output: Path, summary: dict, details: dict) -> None:
    """Спочатку готує всі файли, потім публікує їх; summary є маркером завершення.

    Видаляє лише власні тимчасові файли при помилці. Наявні користувацькі звіти
    не замінює; перед викликом runner перевіряє безпечність розташування output.
    """
    content = {'details.json': json.dumps(details, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
               'comparison.md': render_markdown(summary, details, output),
               'summary.json': json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + '\n'}
    output.mkdir(parents=True, exist_ok=True)
    temporary = []
    try:
        if any(output.iterdir()):
            raise EvaluationError('Output уже не порожній; запис скасовано.')
        for name, body in content.items():
            path = output / (name + '.tmp')
            with path.open('x', encoding='utf-8', newline='\n') as handle:
                handle.write(body)
            temporary.append(path)
        for path in temporary:
            path.rename(output / path.name.removesuffix('.tmp'))
    finally:
        for path in temporary:
            if path.exists():
                path.unlink()
