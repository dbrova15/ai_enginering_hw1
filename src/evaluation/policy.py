"""Явні правила порівняння: однакова політика для всіх моделей і провайдерів.

Aliases означають лише технічні варіанти написання/терміни, не виправлення
фактів. Зміна цього файла змінює policy hash і потребує переоцінювання всіх runs.
"""

POLICY_VERSION = 'golden-evaluator-v1.0'
FORMAT_VERSION = '1.0'
APPROVED_STATUS = 'approved'
PROVISIONAL_BANNER = 'Evaluation status: provisional (golden labels not fully approved)'

# У кожному namespace еквівалентності обмежені його призначенням.
ALIASES = {
    'entity': {
        'arduino uno': ('arduino uno',),
        'relay': ('relay', 'реле'),
        'capacitor': ('capacitor', 'конденсатор'),
        'resistor': ('resistor', 'резистор'),
        'pump': ('pump', 'помпа', 'насос'),
        'voltage': ('voltage', 'напруга'),
        'current': ('current', 'струм'),
        'control distance': ('control distance', 'дальність керування'),
    },
    'interfaces_protocols': {
        'i2c': ('i2c', 'i²c', 'iic'),
        'wi-fi': ('wi-fi', 'wifi', 'wi fi'),
    },
    'software_tools': {
        'arduino ide': ('arduino ide',),
        'c++': ('c++', 'с++'),
    },
}

CONTEXT_MARKERS = {
    'desired': ('desired', 'бажан', 'цільов', 'target'),
    'measured': ('measured', 'вимірян', 'замірян'),
    'declared': ('declared', 'заявлен'),
    'nominal': ('nominal', 'номінальн'),
    'example': ('example', 'приклад'),
    'typical': ('typical', 'типов'),
}

SOURCE_CONFLICTS = {
    'HR-0207': {
        'sha256': '73346dfb6627121c20bfa5584aecd207a89bfe26e31b9cc77aa14b821debb25e',
        'models': ['lm7508', 'lm7805'],
        'evidence': ['стабілізатор lm7508', 'Стабілізатор lm7805'],
        'rule': 'golden-annotation-rules-v1.0 / HR-0207: model=null',
    },
}
