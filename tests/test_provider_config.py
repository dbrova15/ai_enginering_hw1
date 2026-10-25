"""Перевірка вибору провайдера й незалежності двох наборів ключів та моделей."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.config import ConfigError, load_settings


class ProviderConfigTests(unittest.TestCase):
    """Перевіряє конфігурацію двох сервісів без читання приватного .env.

    Кожен тест задає вигадані ключі в ізольованому оточенні. Тимчасові файли
    видаляються після перевірки, справжнє оточення автоматично відновлюється.
    Жоден із цих тестів не створює HTTP-запиту.
    """

    def test_missing_empty_and_explicit_openrouter(self):
        """Зберігає OpenRouter типовим для старого .env та порожнього selector.

        Перевіряє відсутню змінну, порожній рядок, пробіли й явний OpenRouter
        зі змішаним регістром. OpenAI-налаштувань у цих сценаріях немає.
        """
        with tempfile.TemporaryDirectory() as folder:
            for value in (None, '', '   ', ' OpenRouter '):
                env = {'OPENROUTER_API_KEY': 'router-key', 'OPENROUTER_MODEL': 'router/model'}
                if value is not None:
                    env['LLM_PROVIDER'] = value
                with self.subTest(selector=value), patch.dict(os.environ, env, clear=True):
                    loaded = load_settings(Path(folder) / 'absent.env')
                self.assertEqual(loaded.provider, 'openrouter')
                self.assertEqual(loaded.api_key.get_secret_value(), 'router-key')
                self.assertEqual(loaded.model, 'router/model')

    def test_openai_reads_only_its_credentials(self):
        """Дозволяє прямий OpenAI без налаштувань OpenRouter.

        Також перевіряє, що неправильні значення неактивного сервісу не
        блокують запуск і ніколи не підставляються замість активного ключа.
        """
        with tempfile.TemporaryDirectory() as folder:
            for inactive in ({}, {'OPENROUTER_API_KEY': '', 'OPENROUTER_MODEL': 'sk-wrong'}):
                env = {'LLM_PROVIDER': ' OpenAI ', 'OPENAI_API_KEY': 'openai-key',
                       'OPENAI_MODEL': 'openai-model', **inactive}
                with self.subTest(inactive=inactive), patch.dict(os.environ, env, clear=True):
                    loaded = load_settings(Path(folder) / 'absent.env')
                self.assertEqual(loaded.provider, 'openai')
                self.assertEqual(loaded.model, 'openai-model')
                self.assertEqual(loaded.api_key.get_secret_value(), 'openai-key')
                self.assertNotIn('openai-key', repr(loaded))

    def test_openrouter_ignores_invalid_openai_values(self):
        """Не вимагає й не перевіряє credentials неактивного OpenAI.

        Типовий OpenRouter повинен зберігати свої модель і ключ, навіть якщо
        OPENAI_MODEL випадково містить заглушку чи помилкове значення.
        """
        env = {'OPENROUTER_API_KEY': 'router-key', 'OPENROUTER_MODEL': 'router/model',
               'OPENAI_API_KEY': '', 'OPENAI_MODEL': 'sk-wrong'}
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, env, clear=True):
            loaded = load_settings(Path(folder) / 'absent.env')
        self.assertEqual(loaded.provider, 'openrouter')
        self.assertEqual(loaded.model, 'router/model')

    def test_unknown_provider_does_not_fall_back_or_leak_value(self):
        """Невідомий selector має бути помилкою, а не перемиканням на OpenRouter.

        Як selector навмисно подається вигаданий секрет, щоб перевірити:
        повідомлення пояснює допустимі варіанти, не повторюючи вхідне значення.
        """
        env = {'LLM_PROVIDER': 'sk-private-selector', 'OPENROUTER_API_KEY': 'router-key',
               'OPENROUTER_MODEL': 'router/model'}
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ConfigError) as error:
                load_settings(Path(folder) / 'absent.env')
        self.assertIn('LLM_PROVIDER', str(error.exception))
        self.assertNotIn('sk-private-selector', str(error.exception))

    def test_missing_active_credentials_never_use_other_provider(self):
        """Відсутні активні ключ чи модель не беруться з іншого сервісу.

        Перевіряє обидва напрями перемикання та обидві обов'язкові змінні.
        Очікує назву саме відсутнього налаштування активного провайдера.
        """
        with tempfile.TemporaryDirectory() as folder:
            for provider in ('openai', 'openrouter'):
                prefix = provider.upper()
                other = 'OPENROUTER' if provider == 'openai' else 'OPENAI'
                for missing in ('API_KEY', 'MODEL'):
                    env = {'LLM_PROVIDER': provider, f'{prefix}_API_KEY': 'active-key',
                           f'{prefix}_MODEL': 'active-model', f'{other}_API_KEY': 'other-key',
                           f'{other}_MODEL': 'other-model'}
                    del env[f'{prefix}_{missing}']
                    with self.subTest(provider=provider, missing=missing), patch.dict(os.environ, env, clear=True):
                        with self.assertRaises(ConfigError) as error:
                            load_settings(Path(folder) / 'absent.env')
                    self.assertIn(f'{prefix}_{missing}', str(error.exception))

    def test_process_selector_overrides_file_and_keeps_active_file_credentials(self):
        """Перемикає провайдера через оточення поверх налаштувань із .env.

        Ключ і модель OpenAI беруться з тимчасового файла, а selector —
        зі змінної процесу. Інші значення OpenRouter не впливають на результат.
        """
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '.env'
            path.write_text('LLM_PROVIDER=openrouter\nOPENROUTER_API_KEY=router-key\n'
                            'OPENROUTER_MODEL=router/model\nOPENAI_API_KEY=openai-key\n'
                            'OPENAI_MODEL=openai-model\n', encoding='utf-8')
            with patch.dict(os.environ, {'LLM_PROVIDER': 'openai'}, clear=True):
                loaded = load_settings(path)
            self.assertEqual(loaded.provider, 'openai')
            self.assertEqual(loaded.api_key.get_secret_value(), 'openai-key')

    def test_invalid_openai_model_and_placeholder_hide_secret(self):
        """Відхиляє ключ-заглушку й ключ замість ID моделі OpenAI.

        Неправильні значення не повинні перейти до мережі чи з'явитися
        в тексті помилки. Перевірка симетрична попереднім тестам OpenRouter.
        """
        cases = [('sk-...', 'openai-model'), ('openai-key', 'sk-private-model')]
        with tempfile.TemporaryDirectory() as folder:
            for key, model in cases:
                env = {'LLM_PROVIDER': 'openai', 'OPENAI_API_KEY': key, 'OPENAI_MODEL': model}
                with self.subTest(model=model), patch.dict(os.environ, env, clear=True):
                    with self.assertRaises(ConfigError) as error:
                        load_settings(Path(folder) / 'absent.env')
                self.assertNotIn('sk-private-model', str(error.exception))
