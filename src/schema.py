"""Єдиний контракт JSON для моделі, локальної перевірки та майбутнього golden set."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


DocumentType = Literal['project', 'tutorial', 'review', 'comparison', 'theory', 'other']
PrimaryTopic = Literal[
    'devices_automation', 'controllers_programming', 'robotics_actuators',
    'sensors_measurements', 'displays_indicators', 'communications_iot',
    'power_batteries', 'printing_mechanics',
]


class StrictRecord(BaseModel):
    """Спільні правила для об'єктів, які повертає модель.

    Перевіряє передані поля без автоматичного виправлення їхніх типів: число
    замість тексту або сторонній ключ спричиняють помилку валідації. Не читає
    файлів і не звертається до мережі. Нащадки визначають конкретні поля.
    """

    model_config = ConfigDict(extra='forbid', strict=True)


class Component(StrictRecord):
    """Опис одного апаратного компонента, згаданого у статті.

    Зберігає назву, модель, виробника й роль. Усі ключі мають бути присутні,
    але невідомі модель, виробник чи роль позначаються null. Це перевірка
    структури, тому правдивість опису потрібно окремо звіряти з джерелом.
    """

    name: str = Field(description='Назва компонента, підтверджена текстом статті.')
    model: str | None = Field(description='Маркування моделі з тексту або null.')
    manufacturer: str | None = Field(description='Зазначений виробник або null; не вгадувати.')
    role: str | None = Field(description='Підтверджена текстом роль компонента або null.')


class TechnicalParameter(StrictRecord):
    """Одна характеристика пристрою, системи або алгоритму.

    Значення зберігається текстом, щоб не втратити діапазони, знаки нерівності
    та приблизність. Одиниця вимірювання відокремлена від значення. Невідомі
    предмет характеристики й одиниця — null; одиниці автоматично не перераховуються.
    """

    subject: str | None = Field(description='До чого належить характеристика, або null.')
    name: str = Field(description='Назва характеристики з розрізненням виміряного, бажаного й прикладового.')
    value: str = Field(description='Значення без втрати діапазону, межі чи приблизності.')
    unit: str | None = Field(description='Одиниця вимірювання з тексту або null.')


class ExtractionResult(StrictRecord):
    """Вісім погоджених полів, які треба отримати з однієї статті.

    Перевіряє дозволені категорії й структури компонентів та параметрів.
    Відсутні факти позначаються null, а порожні переліки — []. ID документа,
    час, модель і решта службових відомостей зберігаються окремо від цих полів.
    """

    document_type: DocumentType = Field(description='Один тип за домінантною метою статті.')
    primary_topic: PrimaryTopic = Field(description='Одна головна тематика статті з восьми дозволених.')
    main_subject: str | None = Field(description='Головний пристрій, технологія чи алгоритм або null.')
    purpose: str | None = Field(description='Коротке призначення, підтверджене статтею, або null.')
    components: list[Component] = Field(description='Згадані апаратні складники; без домислених характеристик.')
    technical_parameters: list[TechnicalParameter] = Field(description='Технічні характеристики та їхні одиниці.')
    interfaces_protocols: list[str] = Field(description='Інтерфейси та протоколи, які прямо згадані.')
    software_tools: list[str] = Field(description='Згадані мови, бібліотеки, середовища й програмні сервіси.')
