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
    config = types.ModuleType('calibre.utils.config')
    config.tweaks = {
        'per_language_title_sort_articles': {
            'eng': (r'A\s+', r'The\s+', r'An\s+'),
        },
    }

    utils = sys.modules.setdefault('calibre.utils', types.ModuleType('calibre.utils'))
    utils.localization = localization
    utils.config = config
    calibre.constants = constants
    calibre.utils = utils

    sys.modules['calibre.constants'] = constants
    sys.modules['calibre.utils.config'] = config
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
        self.assertTrue(common.goodreads_payload_has_book_data({
            'props': {
                'pageProps': {
                    'apolloState': {
                        'Book:example': {'title': 'Any Goodreads Book'},
                    },
                },
            },
        }))
        self.assertFalse(common.goodreads_payload_has_book_data({
            'props': {'pageProps': {'apolloState': {}}},
        }))

    def test_article_only_setting_is_blank_after_country_removal(self):
        """A title-sort article left by country stripping is not a setting."""
        common = load_module(
            PLUGIN_PACKAGE + '.common',
            os.path.join(ROOT, 'common.py'),
        )
        common.reset_runtime_caches()

        settings, countries = common.format_settings(
            ['The United States'],
            keep_country_in_settings=False,
            keep_region_in_settings=False,
        )

        self.assertEqual([], settings)
        self.assertEqual(['United States'], countries)

    def test_empty_marker_is_replaced_only_when_write_empty_option_is_enabled(self):
        """Real data replaces an Empty marker only when the option owns it."""
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

    def load_worker_process(self, browser_factory):
        calibre = sys.modules['calibre']
        calibre.browser = browser_factory
        sys.modules.pop(PLUGIN_PACKAGE + '.worker_process', None)
        return load_module(
            PLUGIN_PACKAGE + '.worker_process',
            os.path.join(ROOT, 'worker_process.py'),
        )

    def test_waf_challenge_is_reported_without_reading_the_empty_body(self):
        """A Goodreads WAF response should fail safely before parsing its empty body."""
        class ChallengeResponse(object):
            status = 202
            headers = {'x-amzn-waf-action': 'challenge'}

            def __init__(self):
                self.read_called = False

            def read(self):
                self.read_called = True
                return b''

        class ChallengeBrowser(object):
            def __init__(self, response):
                self.response = response
                self.addheaders = []

            def set_handle_robots(self, _enabled):
                pass

            def open(self, _url, timeout=None):
                return self.response

        response = ChallengeResponse()
        browser = ChallengeBrowser(response)
        worker = self.load_worker_process(lambda: browser)

        with self.assertRaisesRegex(
            worker.GoodreadsWafChallengeError,
            'Goodreads is requiring a browser challenge',
        ):
            worker.fetch_goodreads_page('230926478')

        self.assertFalse(response.read_called)
        self.assertEqual(
            [('User-Agent', worker.GOODREADS_USER_AGENT)],
            browser.addheaders,
        )
        header_only_response = type(
            'HeaderOnlyResponse',
            (),
            {
                'status': 200,
                'headers': {'x-amzn-waf-action': 'challenge'},
            },
        )()
        self.assertTrue(worker.is_goodreads_waf_challenge(header_only_response))

    def test_non_ok_response_errors_are_descriptive_and_skip_the_body(self):
        """Every final non-200 Goodreads response should preserve its failure reason."""
        class Response(object):
            def __init__(self, status):
                self.status = status
                self.headers = {}
                self.read_called = False

            def read(self):
                self.read_called = True
                return b''

        class FakeBrowser(object):
            def __init__(self, response):
                self.response = response
                self.addheaders = []

            def set_handle_robots(self, _enabled):
                pass

            def open(self, _url, timeout=None):
                return self.response

        expected_errors = (
            (204, 'no content', False),
            (403, 'denied access', False),
            (404, 'could not find', False),
            (429, 'rate-limiting', True),
            (503, 'temporarily unavailable', True),
        )
        for status, message, retryable in expected_errors:
            response = Response(status)
            worker = self.load_worker_process(lambda: FakeBrowser(response))

            with self.assertRaises(worker.GoodreadsHttpError) as caught:
                worker.fetch_goodreads_page('230926478')

            self.assertEqual(status, caught.exception.status_code)
            self.assertEqual(retryable, caught.exception.retryable)
            self.assertIn(message, str(caught.exception))
            self.assertFalse(response.read_called)

    def test_waf_challenge_skips_only_that_book_and_keeps_existing_fields(self):
        """A blocked book should not receive Empty values or stop later books."""
        worker = self.load_worker_process(lambda: None)
        fetched_ids = []
        build_requests = []

        def fake_fetch(goodreads_id, **_kwargs):
            fetched_ids.append(goodreads_id)
            if goodreads_id == 'blocked':
                raise worker.GoodreadsWafChallengeError(
                    worker.GOODREADS_WAF_CHALLENGE_MESSAGE
                )
            return [], []

        def fake_build_field_updates(*args, **kwargs):
            build_requests.append((args, kwargs))
            return {'#characters': 'Empty'}

        worker.fetch_and_extract_goodreads_data = fake_fetch
        original_build_field_updates = worker.common.build_field_updates
        worker.common.build_field_updates = fake_build_field_updates
        original_sleep = worker.time.sleep
        worker.time.sleep = lambda _seconds: None
        try:
            results = worker.process_goodreads_batch(
                [
                    {'book_id': 1, 'goodreads_id': 'blocked', 'title': 'Blocked'},
                    {'book_id': 2, 'goodreads_id': 'available', 'title': 'Available'},
                ],
                {
                    'query_interval_seconds': 1,
                    'write_empty_to_custom_fields': True,
                    'field_specs': {'character_field': {'field_name': '#characters'}},
                },
            )
        finally:
            worker.time.sleep = original_sleep
            worker.common.build_field_updates = original_build_field_updates

        self.assertEqual(['blocked', 'available'], fetched_ids)
        self.assertEqual({}, results[0]['field_updates'])
        self.assertIn('Goodreads is requiring a browser challenge', results[0]['error'])
        self.assertEqual({'#characters': 'Empty'}, results[1]['field_updates'])
        self.assertEqual(1, len(build_requests))

    def test_200_response_without_book_data_is_an_error_not_an_empty_value(self):
        """A successful HTTP response without Goodreads book data must not write Empty."""
        worker = self.load_worker_process(lambda: None)
        original_fetch_page = worker.fetch_goodreads_page
        original_has_book_data = worker.common.has_goodreads_book_data
        worker.fetch_goodreads_page = lambda _goodreads_id: '<html></html>'
        worker.common.has_goodreads_book_data = lambda _html: False
        try:
            results = worker.process_goodreads_batch(
                [{'book_id': 1, 'goodreads_id': '230926478', 'title': 'No Data'}],
                {
                    'query_interval_seconds': 1,
                    'retry_attempts': 1,
                    'write_empty_to_custom_fields': True,
                    'field_specs': {'character_field': {'field_name': '#characters'}},
                },
            )
        finally:
            worker.fetch_goodreads_page = original_fetch_page
            worker.common.has_goodreads_book_data = original_has_book_data

        self.assertEqual({}, results[0]['field_updates'])
        self.assertIn('without usable book data', results[0]['error'])

    def test_simulated_error_skips_fetching_and_field_updates(self):
        """The UI simulation setting should reproduce errors without contacting Goodreads."""
        worker = self.load_worker_process(lambda: None)
        original_fetch = worker.fetch_and_extract_goodreads_data

        def unexpected_fetch(*_args, **_kwargs):
            self.fail('A simulated error must not fetch Goodreads.')

        worker.fetch_and_extract_goodreads_data = unexpected_fetch
        try:
            results = worker.process_goodreads_batch(
                [{'book_id': 1, 'goodreads_id': '230926478', 'title': 'Simulated'}],
                {
                    'query_interval_seconds': 1,
                    'debug_simulated_error': 'missing_book_data',
                    'write_empty_to_custom_fields': True,
                    'field_specs': {'character_field': {'field_name': '#characters'}},
                },
            )
        finally:
            worker.fetch_and_extract_goodreads_data = original_fetch

        self.assertEqual({}, results[0]['field_updates'])
        self.assertIn('without usable book data', results[0]['error'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
