"""Явні правила порівняння: однакова політика для всіх моделей і провайдерів.

Aliases означають лише технічні варіанти написання/терміни, не виправлення
фактів. Зміна цього файла змінює policy hash і потребує переоцінювання всіх runs.
"""

POLICY_VERSION = 'golden-evaluator-v2.0'
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
    'desired': ('desired', 'бажан', 'цільов', 'target', 'желаем', 'целев'),
    'measured': ('measured', 'вимірян', 'замірян', 'измеренн'),
    'declared': ('declared', 'заявлен', 'заявленн'),
    'nominal': ('nominal', 'номінальн', 'номинальн'),
    'example': ('example', 'приклад', 'пример'),
    'typical': ('typical', 'типов', 'типичн'),
}

# Обмежені загальні технічні поняття. Варіанти означають повний термін,
# а не substring: зайва функція або кваліфікатор не відкидається.
ENTITY_CONCEPTS = {
    'battery': ('battery', 'акумулятор', 'аккумулятор'),
    'tilt_module': ('tilt sensor module', 'модуль датчика наклона', 'модуль датчика нахилу'),
    'ball_tilt_sensor': ('ball tilt sensor', 'шариковый датчик наклона', 'кульковий датчик нахилу'),
    'module_board': ('module circuit board', 'module board', 'печатная плата модуля', 'плата модуля', 'друкована плата модуля'),
    'arduino_uno': ('arduino uno', 'плата arduino uno'),
    'arduino_mega': ('arduino mega', 'плата arduino mega'),
    'arduino_uno_rev3': ('arduino uno rev.3', 'плата arduino uno rev.3'),
    'microcontroller': ('microcontroller', 'мікроконтролер', 'микроконтроллер'),
    'relay': ('relay', 'реле'),
    'battery': ('battery', 'акумулятор', 'аккумулятор'),
    'capacitor': ('capacitor', 'конденсатор'),
    'resistor': ('resistor', 'резистор'),
    'pump': ('pump', 'помпа', 'насос'),
    'potentiometer': ('potentiometer', 'потенціометр', 'потенциометр'),
    'jumpers': ('jumper wires', 'jumpers', 'перемички', 'перемычки'),
    'usb_cable': ('usb cable', 'usb-кабель'),
    'voltage_regulator': ('voltage regulator', 'стабілізатор напруги', 'стабилизатор напряжения'),
    'voltage_comparator': ('voltage comparator', 'компаратор напруги', 'компаратор напряжения'),
    'watering_system': ('automatic plant watering system', 'система автоматичного поливу рослин', 'система автоматического полива растений'),
}

PROPERTY_CONCEPTS = {
    'voltage': ('voltage', 'напруга', 'напряжение'),
    'operating_voltage': ('operating voltage', 'working voltage', 'робоча напруга', 'рабочее напряжение'),
    'supply_voltage': ('supply voltage', 'напруга живлення', 'напряжение питания'),
    'current': ('current', 'струм', 'ток'),
    'current_consumption': ('current consumption', 'споживаний струм', 'струм споживання', 'потребляемый ток'),
    'dimensions': ('dimensions', 'size', 'розміри', 'размеры'),
    'board_dimensions': ('board size', 'board dimensions', 'розміри плати', 'размеры платы'),
    'threshold_angle': ('threshold angle', 'threshold angle range', 'діапазон порогового кута', 'пороговий кут', 'диапазон порогового угла', 'пороговый угол'),
    'angle_range': ('angle range', 'діапазон кутів', 'диапазон углов'),
    'pin_number': ('pin number', 'номер піна', 'номер пина'),
    'contact_count': ('contact count', 'number of contacts', 'кількість контактів', 'количество контактов'),
    'capacitance': ('capacitance', 'ємність', 'ёмкость', 'емкость'),
    'frequency': ('frequency', 'частота'),
    'power': ('power', 'потужність', 'мощность'),
    'output_voltage': ('output voltage', 'вихідна напруга', 'выходное напряжение'),
    'input_voltage': ('input voltage', 'вхідна напруга', 'входное напряжение'),
    'voltage_drop': ('voltage drop', 'падіння напруги', 'падение напряжения'),
    'range': ('range', 'дальність', 'дальность'),
}

PROPERTY_FAMILIES = {
    'operating_voltage': 'voltage', 'supply_voltage': 'voltage',
    'output_voltage': 'voltage', 'input_voltage': 'voltage', 'voltage_drop': 'voltage',
    'current_consumption': 'current', 'board_dimensions': 'dimensions',
    'threshold_angle': 'angle', 'angle_range': 'angle',
}

ROLE_CONCEPTS = {
    'plant_watering': ('plant watering', 'полив рослин', 'полив растений'),
    'temperature_measurement': ('temperature measurement', 'вимірювання температури', 'измерение температуры'),
    'power_supply': ('power supply', 'живлення', 'питание'),
    'connection': ('connection', "з'єднання", 'соединение'),
    'sensor': ('sensor', 'датчик', 'сенсор'),
    'controller': ('controller', 'контролер', 'контроллер'),
}

STATEMENT_CONCEPTS = {
    'automatic_plant_watering': ('automatic plant watering', 'автоматичний полив рослин', 'автоматический полив растений'),
    'temperature_measurement': ROLE_CONCEPTS['temperature_measurement'],
}

SOURCE_CONFLICTS = {
    'HR-0207': {
        'sha256': '73346dfb6627121c20bfa5584aecd207a89bfe26e31b9cc77aa14b821debb25e',
        'models': ['lm7508', 'lm7805'],
        'evidence': ['стабілізатор lm7508', 'Стабілізатор lm7805'],
        'rule': 'golden-annotation-rules-v1.0 / HR-0207: model=null',
    },
}
