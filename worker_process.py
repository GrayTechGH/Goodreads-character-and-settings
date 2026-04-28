#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2026, GrayTechGH'
__docformat__ = 'restructuredtext en'

try:
    load_translations()
except NameError:
    pass

try:
    _
except NameError:
    def _(text):
        return text

import time

from calibre import browser

from calibre_plugins.Goodreads_character_and_settings import common


GOODREADS_BASE_URL = 'https://www.goodreads.com'


def fetch_goodreads_page(goodreads_id, timeout=30):
    url = '{}/book/show/{}'.format(GOODREADS_BASE_URL, goodreads_id)
    try:
        br = browser()
        br.set_handle_robots(False)
        response = br.open(url, timeout=timeout)
        raw = response.read()
    except Exception as err:
        raise RuntimeError(_('Error while fetching {}: {}').format(url, err))

    return raw.decode('utf-8', errors='replace')


def fetch_and_extract_goodreads_data(goodreads_id, retry_attempts=3, retry_delay_seconds=2):
    last_error = None

    for attempt in range(1, retry_attempts + 1):
        try:
            html = fetch_goodreads_page(goodreads_id)
            characters = common.extract_goodreads_values(html, 'Characters')
            settings = common.extract_goodreads_values(html, 'Setting')
            if characters or settings or attempt >= retry_attempts:
                return characters, settings
        except Exception as err:
            last_error = err
            if attempt >= retry_attempts:
                raise

        if attempt < retry_attempts:
            time.sleep(retry_delay_seconds)

    if last_error is not None:
        raise last_error
    return [], []


def process_goodreads_batch(books, options, notification=lambda *_args: None):
    interval_seconds = max(1, int(options.get('query_interval_seconds', 30)))
    keep_country_in_settings = options.get(
        'include_country_with_location',
        True,
    )
    keep_region_in_settings = options.get('keep_region_in_settings', True)
    debug_character_sources = options.get('debug_character_sources', False)
    debug_settings_pipeline = options.get('debug_settings_pipeline', False)
    write_empty_to_custom_fields = options.get('write_empty_to_custom_fields', False)
    field_specs = options.get('field_specs', {})
    retry_attempts = max(1, int(options.get('retry_attempts', 3)))
    retry_delay_seconds = max(1, int(options.get('retry_delay_seconds', 2)))
    results = []
    total = max(1, len(books))

    for index, book in enumerate(books):
        if index:
            time.sleep(interval_seconds)

        result = {
            'book_id': book['book_id'],
            'field_updates': {},
            'debug_characters': [],
            'debug_settings': {},
            'error': '',
        }
        try:
            characters, settings = fetch_and_extract_goodreads_data(
                book['goodreads_id'],
                retry_attempts=retry_attempts,
                retry_delay_seconds=retry_delay_seconds,
            )
            formatted_settings, countries = common.format_settings(
                settings,
                keep_country_in_settings=keep_country_in_settings,
                keep_region_in_settings=keep_region_in_settings,
            )
            result['field_updates'] = common.build_field_updates(
                book.get('existing_fields', {}),
                field_specs,
                {
                    'character_field': characters,
                    'settings_field': formatted_settings,
                    'countries_field': countries,
                },
                write_empty_to_custom_fields=write_empty_to_custom_fields,
            )
            if debug_character_sources:
                result['debug_characters'] = list(
                    common._LAST_EXTRACTION_DEBUG.get('characters', [])
                )
            if debug_settings_pipeline:
                lookup, patterns = common.load_country_variant_data()
                result['debug_settings'] = {
                    'country_variant_source': common._COUNTRY_VARIANT_SOURCE,
                    'country_variant_lookup_size': len(lookup or {}),
                    'country_variant_pattern_size': len(patterns or []),
                    'raw_settings': list(settings or []),
                    'formatted_settings': list(formatted_settings or []),
                    'countries': list(countries or []),
                    'field_updates': dict(result['field_updates']),
                }
        except Exception as err:
            result['error'] = str(err)

        results.append(result)
        try:
            notification(
                float(index + 1) / float(total),
                book.get('title', _('Processing Goodreads book')),
            )
        except Exception:
            pass

    return results
