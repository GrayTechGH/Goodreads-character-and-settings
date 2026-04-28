#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


from __future__ import print_function

import importlib.util
import io
import json
import os
import sys
import tempfile
import types
import unittest
import zipfile
from contextlib import redirect_stdout


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN_PACKAGE = 'calibre_plugins.Goodreads_character_and_settings'


def load_module(module_name, path):
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def install_fake_calibre_modules(config_dir):
    calibre = sys.modules.setdefault('calibre', types.ModuleType('calibre'))
    constants = types.ModuleType('calibre.constants')
    constants.config_dir = config_dir

    localization = types.ModuleType('calibre.utils.localization')
    localization.get_lang = lambda: 'en'
    localization.available_translations = lambda: ['en', 'fr', 'de']
    localization.countrycode_to_name = lambda code: code
    localization.get_language = lambda code: code

    utils = sys.modules.setdefault('calibre.utils', types.ModuleType('calibre.utils'))
    utils.localization = localization
    calibre.constants = constants
    calibre.utils = utils

    sys.modules['calibre.constants'] = constants
    sys.modules['calibre.utils.localization'] = localization


def install_plugin_package():
    sys.modules.setdefault('calibre_plugins', types.ModuleType('calibre_plugins'))
    package = sys.modules.setdefault(PLUGIN_PACKAGE, types.ModuleType(PLUGIN_PACKAGE))
    package.__path__ = [ROOT]
    return package


class PluginSmokeTests(unittest.TestCase):
    """Readable smoke tests for resource and localization behavior."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        install_fake_calibre_modules(self.temp_dir.name)
        install_plugin_package()
        self.settings_data = load_module(
            PLUGIN_PACKAGE + '.settings_data',
            os.path.join(ROOT, 'settings_data.py'),
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_resource_validator_passes_with_current_json_files(self):
        """All bundled JSON resources should pass the development validator."""
        validator = load_module(
            'dev_tools.validate_resources',
            os.path.join(ROOT, 'dev_tools', 'validate_resources.py'),
        )
        self.assertEqual(0, validator.main())

    def test_plugin_zip_excludes_development_helpers(self):
        """The release zip should not include dev_tools or standalone debug helpers."""
        zip_path = os.path.join(ROOT, 'Goodreads-character-and-settings.zip')
        self.assertTrue(os.path.exists(zip_path), 'Expected plugin zip to exist at {}'.format(zip_path))

        with zipfile.ZipFile(zip_path, 'r') as zf:
            names = set(zf.namelist())

        self.assertFalse(
            any(name.startswith('dev_tools/') for name in names),
            'Release zip must not include dev_tools/',
        )
        self.assertNotIn(
            'debug_supported_languages.py',
            names,
            'Release zip must not include the development-only language debugger at plugin root.',
        )
        for required in (
            'resources/default_country_names.json',
            'resources/default_country_regions.json',
            'resources/plugin_ui_translations.json',
        ):
            self.assertIn(required, names, 'Release zip is missing {}'.format(required))

    def test_falkland_islands_short_name_keeps_malvinas_as_alias(self):
        """FK should display as Falkland Islands while still matching the ISO formal name."""
        data = self.settings_data.build_default_user_data(
            country_name_language=self.settings_data.COUNTRY_NAME_LANGUAGE_ENGLISH_SHORT,
            country_name_mode=self.settings_data.COUNTRY_NAME_MODE_ALIAS,
        )
        falkland = next(country for country in data['countries'] if country['iso'] == 'FK')

        self.assertEqual('Falkland Islands', falkland['country'])
        self.assertIn('Falkland Islands (Malvinas)', falkland['aliases'])

    def test_localized_country_mode_uses_selected_language_as_country_value(self):
        """Country mode should write the selected-language country name as the country value."""
        data = self.settings_data.build_default_user_data(
            country_name_language='fr',
            country_name_mode=self.settings_data.COUNTRY_NAME_MODE_COUNTRY,
        )
        united_states = next(country for country in data['countries'] if country['iso'] == 'US')

        self.assertEqual('États-Unis', united_states['country'])
        self.assertIn('United States', united_states['aliases'])
        self.assertIn('United States of America', united_states['aliases'])

    def test_ensure_user_json_files_writes_human_editable_defaults(self):
        """First-run setup should create readable user JSON files with schema versions."""
        self.settings_data.ensure_user_json_files(force_reset=True)

        expected_files = (
            self.settings_data.countries_json_path(),
            self.settings_data.regions_json_path(),
            self.settings_data.autodelete_json_path(),
        )
        for path in expected_files:
            self.assertTrue(os.path.exists(path), 'Expected first-run setup to create {}'.format(path))
            with open(path, 'r', encoding='utf-8') as f:
                payload = json.load(f)
            self.assertEqual(
                self.settings_data.USER_DATABASE_SCHEMA_VERSION,
                payload.get('schema_version'),
                '{} should carry the current schema version'.format(path),
            )

    def test_plugin_ui_text_prefers_calibre_translation_then_json_fallback(self):
        """Plugin UI text should use native Calibre text first, then plugin JSON by language."""
        common = load_module(
            PLUGIN_PACKAGE + '.common',
            os.path.join(ROOT, 'common.py'),
        )
        common._PLUGIN_UI_TRANSLATIONS = {
            'fr': {
                'About': 'À propos',
                'Customize plugin...': "Personnaliser l'extension...",
            }
        }
        common.active_language_code = lambda: 'fr_CA'
        common.is_running_under_calibre_debug = lambda: False

        self.assertEqual(
            'Natif',
            common.plugin_ui_text('About', lambda text: 'Natif' if text == 'About' else text),
        )
        self.assertEqual('À propos', common.plugin_ui_text('About'))
        self.assertEqual('Untranslated', common.plugin_ui_text('Untranslated'))

    def test_plugin_ui_translation_debug_reports_missing_language_once(self):
        """Missing plugin UI language maps should be visible in debug output without log spam."""
        common = load_module(
            PLUGIN_PACKAGE + '.common',
            os.path.join(ROOT, 'common.py'),
        )
        common._PLUGIN_UI_TRANSLATIONS = {'en': {'About': 'About'}}
        common._PLUGIN_UI_TRANSLATION_DEBUG_MESSAGES.clear()
        common.active_language_code = lambda: 'zz_ZZ'
        common.is_running_under_calibre_debug = lambda: True

        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual('About', common.plugin_ui_text('About'))
            self.assertEqual('About', common.plugin_ui_text('About'))

        self.assertEqual(
            1,
            output.getvalue().count("no plugin UI translations for language 'zz_ZZ'"),
            'Missing language debug output should be printed once per session.',
        )

    def test_plugin_ui_translation_debug_reports_missing_text_once(self):
        """Missing plugin UI strings should be visible in debug output without log spam."""
        common = load_module(
            PLUGIN_PACKAGE + '.common',
            os.path.join(ROOT, 'common.py'),
        )
        common._PLUGIN_UI_TRANSLATIONS = {'fr': {'About': 'À propos'}}
        common._PLUGIN_UI_TRANSLATION_DEBUG_MESSAGES.clear()
        common.active_language_code = lambda: 'fr'
        common.is_running_under_calibre_debug = lambda: True

        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual('Customize plugin...', common.plugin_ui_text('Customize plugin...'))
            self.assertEqual('Customize plugin...', common.plugin_ui_text('Customize plugin...'))

        self.assertEqual(
            1,
            output.getvalue().count("no plugin UI translation for 'Customize plugin...' in language 'fr'"),
            'Missing text debug output should be printed once per session.',
        )

    def test_plugin_ui_translation_debug_is_quiet_outside_calibre_debug(self):
        """Missing plugin UI translations should not print outside calibre-debug."""
        common = load_module(
            PLUGIN_PACKAGE + '.common',
            os.path.join(ROOT, 'common.py'),
        )
        common._PLUGIN_UI_TRANSLATIONS = {'en': {'About': 'About'}}
        common._PLUGIN_UI_TRANSLATION_DEBUG_MESSAGES.clear()
        common.active_language_code = lambda: 'zz_ZZ'
        common.is_running_under_calibre_debug = lambda: False

        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual('About', common.plugin_ui_text('About'))

        self.assertEqual('', output.getvalue())

    def test_calibre_debug_detection_checks_executable_and_arguments(self):
        """calibre-debug detection should work from executable names or argv entries."""
        common = load_module(
            PLUGIN_PACKAGE + '.common',
            os.path.join(ROOT, 'common.py'),
        )
        original_argv = list(sys.argv)
        original_executable = sys.executable
        try:
            sys.argv = ['calibre-debug.exe', '-g']
            sys.executable = 'python.exe'
            self.assertTrue(common.is_running_under_calibre_debug())

            sys.argv = ['python.exe', 'calibre-debug']
            sys.executable = 'python.exe'
            self.assertTrue(common.is_running_under_calibre_debug())

            sys.argv = ['calibre.exe']
            sys.executable = 'python.exe'
            self.assertFalse(common.is_running_under_calibre_debug())
        finally:
            sys.argv = original_argv
            sys.executable = original_executable

    def test_common_value_helpers_keep_lists_clean_and_predictable(self):
        """Common value cleanup should remove markup, whitespace noise, and duplicate values."""
        common = load_module(
            PLUGIN_PACKAGE + '.common',
            os.path.join(ROOT, 'common.py'),
        )

        self.assertEqual('London', common.cleanup_value(' <b>London</b>&nbsp; '))
        self.assertEqual(
            ['London', 'Paris'],
            common.merge_unique_values([' London ', 'Paris'], ['london', 'Paris']),
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
