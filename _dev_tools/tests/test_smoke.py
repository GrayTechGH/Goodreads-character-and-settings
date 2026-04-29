#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


from __future__ import print_function

import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
import zipfile


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
            '_dev_tools.validate_resources',
            os.path.join(ROOT, '_dev_tools', 'validate_resources.py'),
        )
        self.assertEqual(0, validator.main())

    def test_plugin_zip_excludes_development_helpers(self):
        """The release zip should not include _dev_tools or standalone debug helpers."""
        zip_path = os.path.join(ROOT, 'Goodreads-character-and-settings.zip')
        self.assertTrue(os.path.exists(zip_path), 'Expected plugin zip to exist at {}'.format(zip_path))

        with zipfile.ZipFile(zip_path, 'r') as zf:
            names = set(zf.namelist())

        self.assertFalse(
            any(name.startswith('_dev_tools/') for name in names),
            'Release zip must not include _dev_tools/',
        )
        self.assertNotIn(
            'debug_supported_languages.py',
            names,
            'Release zip must not include the development-only language debugger at plugin root.',
        )
        for required in (
            'resources/default_country_names.json',
            'resources/default_country_regions.json',
            'translations/fr.mo',
            'translations/ar.mo',
            'translations/en.mo',
        ):
            self.assertIn(required, names, 'Release zip is missing {}'.format(required))

    def test_translation_validator_passes_with_current_catalogs(self):
        """Generated gettext catalogs should have matching source and runtime coverage."""
        validator = load_module(
            '_dev_tools.validate_translations',
            os.path.join(ROOT, '_dev_tools', 'validate_translations.py'),
        )
        self.assertEqual(0, validator.main())

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

    def test_empty_marker_is_replaced_only_when_write_empty_option_is_enabled(self):
        """Real Goodreads values should replace Empty only when that option owns the marker."""
        common = load_module(
            PLUGIN_PACKAGE + '.common',
            os.path.join(ROOT, 'common.py'),
        )
        field_specs = {
            'settings_field': {
                'field_name': '#settings',
                'is_tags': False,
                'is_multiple': True,
            },
        }
        existing_fields = {'#settings': ['Empty']}
        extracted_values = {'settings_field': ['London']}

        self.assertEqual(
            {'#settings': ['London']},
            common.build_field_updates(
                existing_fields,
                field_specs,
                extracted_values,
                write_empty_to_custom_fields=True,
            ),
        )
        self.assertEqual(
            {'#settings': ['Empty', 'London']},
            common.build_field_updates(
                existing_fields,
                field_specs,
                extracted_values,
                write_empty_to_custom_fields=False,
            ),
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
