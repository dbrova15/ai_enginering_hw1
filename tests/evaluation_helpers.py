"""Синтетичні дані оцінювача: жодних викликів моделей або підміни golden set."""

import copy
import json
from pathlib import Path


def extraction(**changes) -> dict:
    """Створює мінімальний валідний прогноз із можливістю змінити окремі поля."""
    return {'document_type': 'project', 'primary_topic': 'devices_automation',
            'main_subject': None, 'purpose': None, 'components': [], 'technical_parameters': [],
            'interfaces_protocols': [], 'software_tools': [], **changes}


def component(name='relay', model=None, manufacturer=None, role=None) -> dict:
    """Створює один компонент для перевірки сутності та незалежних атрибутів."""
    return dict(name=name, model=model, manufacturer=manufacturer, role=role)


def parameter(value='12', unit='V', subject='battery', name='voltage') -> dict:
    """Створює характеристику, явно прив’язану до предмета та назви величини."""
    return dict(subject=subject, name=name, value=value, unit=unit)


def run_data(doc='D1', result=None, **changes) -> dict:
    """Готує envelope із однією генерацією та відомим HTTP usage для тесту."""
    result = extraction() if result is None else result
    usage = {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15,
             'prompt_tokens_details': {'cached_tokens': 0}}
    attempt = {'returned_model': 'test-model-v1', 'result': copy.deepcopy(result),
               'usage': usage, 'requests': [{'response': {'usage': copy.deepcopy(usage)}}]}
    return {'document_id': doc, 'provider': 'test', 'requested_model': 'test-model',
            'schema_version': 'v1', 'prompt': {'version': 'v1', 'sha256': 'a' * 64},
            'sampling': {'temperature': 0, 'top_p': 1}, 'limits': {},
            'status': 'success', 'first_pass_valid': True, 'latency_seconds': 2,
            'attempts': [attempt], 'result': result, **changes}


def write_json(path: Path, value) -> None:
    """Записує ізольовану UTF-8 фікстуру, не торкаючись реального корпусу."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


def workspace(root: Path, status='approved') -> tuple:
    """Створює повний малий набір входів для CLI в тимчасовому каталозі."""
    golden, runs, manifest, rules = (root / p for p in ['golden.json', 'runs', 'manifest.json', 'rules.md'])
    write_json(golden, [{'document_id': 'D1', 'annotation_status': status, 'expected': extraction()}])
    write_json(runs / 'run_one.json', run_data())
    write_json(manifest, [{'id': 'D1'}])
    rules.write_text('Тестові правила', encoding='utf-8')
    return golden, runs, manifest, rules
