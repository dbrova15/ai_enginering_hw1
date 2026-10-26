"""Проста схема тегування підтверджених згадок у технічній статті."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from src.schema import PrimaryTopic

Language = Literal['uk', 'en', 'ru']
Platform = Literal['arduino', 'esp32', 'esp8266', 'stm32', 'raspberry_pi', 'orange_pi']
Interface = Literal['wifi', 'bluetooth', 'lora', 'i2c', 'spi', 'uart', 'usb']
PLATFORMS = ('arduino', 'esp32', 'esp8266', 'stm32', 'raspberry_pi', 'orange_pi')
INTERFACES = ('wifi', 'bluetooth', 'lora', 'i2c', 'spi', 'uart', 'usb')


class ExtractionResultV2(BaseModel):
    """Вісім обов’язкових полів без null, довільних значень і неявної конвертації.

    Списки приймають довільний порядок, але повертаються в порядку enum.
    Дублікати є помилкою відповіді, тому не видаляються мовчки. Сортування
    result не змінює збереженої сирої відповіді моделі.
    """

    model_config = ConfigDict(extra='forbid', strict=True)

    language: Language
    primary_topic: PrimaryTopic
    mentioned_platforms: list[Platform]
    mentioned_interfaces: list[Interface]
    mentions_sensor: bool
    mentions_display: bool
    mentions_battery: bool
    mentions_motor: bool

    @field_validator('mentioned_platforms', 'mentioned_interfaces')
    @classmethod
    def canonical_tags(cls, values: list[str], info) -> list[str]:
        """Відхиляє повтор тегу й повертає новий список у сталому enum-порядку."""
        if len(values) != len(set(values)):
            raise ValueError('Теги у списку повинні бути унікальними.')
        order = PLATFORMS if info.field_name == 'mentioned_platforms' else INTERFACES
        return sorted(values, key=order.index)
