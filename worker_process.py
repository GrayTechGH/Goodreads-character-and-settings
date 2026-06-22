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
GOODREADS_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 Chrome/125 Safari/537.36'
)
GOODREADS_WAF_CHALLENGE_MESSAGE = (
    'Goodreads is requiring a browser challenge and returned no usable book page.'
)
GOODREADS_MISSING_BOOK_DATA_MESSAGE = (
    'Goodreads returned a 200 response without usable book data.'
)
GOODREADS_HTTP_ERROR_MESSAGES = {
    204: 'Goodreads returned no content for this book page.',
    401: 'Goodreads requires sign-in to access this book page.',
    403: 'Goodreads denied access to this book page.',
    404: 'Goodreads could not find this book page.',
    408: 'Goodreads timed out while handling this request.',
    410: 'This Goodreads book page is no longer available.',
    429: 'Goodreads is temporarily rate-limiting requests.',
}
RETRYABLE_HTTP_STATUS_CODES = frozenset((408, 429, 500, 502, 503, 504))


class GoodreadsFetchError(RuntimeError):

    def __init__(self, message, retryable=False):
        RuntimeError.__init__(self, message)
        self.retryable = retryable


class GoodreadsWafChallengeError(GoodreadsFetchError):
    pass


class GoodreadsHttpError(GoodreadsFetchError):

    def __init__(self, status_code, message, retryable=False):
        GoodreadsFetchError.__init__(self, message, retryable=retryable)
        self.status_code = status_code


class GoodreadsPageDataError(GoodreadsFetchError):
    pass


def simulated_goodreads_error(value):
    if value == 'waf_challenge':
        return GoodreadsWafChallengeError(GOODREADS_WAF_CHALLENGE_MESSAGE)
    if value == 'not_found':
        return GoodreadsHttpError(404, GOODREADS_HTTP_ERROR_MESSAGES[404])
    if value == 'access_denied':
        return GoodreadsHttpError(403, GOODREADS_HTTP_ERROR_MESSAGES[403])
    if value == 'rate_limited':
        return GoodreadsHttpError(
            429,
            GOODREADS_HTTP_ERROR_MESSAGES[429],
            retryable=True,
        )
    if value == 'missing_book_data':
        return GoodreadsPageDataError(GOODREADS_MISSING_BOOK_DATA_MESSAGE)
    return None


def response_status_code(response):
    for attribute in ('status', 'code'):
        value = getattr(response, attribute, None)
        if callable(value):
            value = value()
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            pass

    getcode = getattr(response, 'getcode', None)
    if callable(getcode):
        try:
            return int(getcode())
        except (TypeError, ValueError):
            pass
    return None


def response_header(response, name):
    headers = getattr(response, 'headers', None)
    if headers is None:
        info = getattr(response, 'info', None)
        headers = info() if callable(info) else None
    if headers is None:
        return ''

    get = getattr(headers, 'get', None)
    if callable(get):
        return str(get(name, '') or '')
    return ''


def is_goodreads_waf_challenge(response):
    if response_status_code(response) == 202:
        return True
    return 'challenge' in response_header(response, 'x-amzn-waf-action').lower()


def goodreads_response_error(response):
    status_code = response_status_code(response)
    if is_goodreads_waf_challenge(response):
        return GoodreadsWafChallengeError(GOODREADS_WAF_CHALLENGE_MESSAGE)
    if status_code is None or status_code == 200:
        return None

    message = GOODREADS_HTTP_ERROR_MESSAGES.get(status_code)
    if message is None and 500 <= status_code <= 599:
        message = 'Goodreads is temporarily unavailable (HTTP {}).'.format(status_code)
    elif message is None:
        message = 'Goodreads returned an unusable response (HTTP {}).'.format(status_code)
    return GoodreadsHttpError(
        status_code,
        message,
        retryable=status_code in RETRYABLE_HTTP_STATUS_CODES,
    )


def fetch_goodreads_page(goodreads_id, timeout=30):
    url = '{}/book/show/{}'.format(GOODREADS_BASE_URL, goodreads_id)
    try:
        br = browser()
        br.set_handle_robots(False)
        br.addheaders = [('User-Agent', GOODREADS_USER_AGENT)]
        response = br.open(url, timeout=timeout)
        response_error = goodreads_response_error(response)
        if response_error is not None:
            raise response_error
        raw = response.read()
    except GoodreadsFetchError:
        raise
    except Exception as err:
        response_error = goodreads_response_error(err)
        if response_error is not None:
            raise response_error
        raise RuntimeError(_('Error while fetching {}: {}').format(url, err))

    return raw.decode('utf-8', errors='replace')


def fetch_and_extract_goodreads_data(goodreads_id, retry_attempts=3, retry_delay_seconds=2):
    last_error = None

    for attempt in range(1, retry_attempts + 1):
        try:
            html = fetch_goodreads_page(goodreads_id)
            if not common.has_goodreads_book_data(html):
                raise GoodreadsPageDataError(GOODREADS_MISSING_BOOK_DATA_MESSAGE)
            characters = common.extract_goodreads_values(html, 'Characters')
            settings = common.extract_goodreads_values(html, 'Setting')
            if characters or settings or attempt >= retry_attempts:
                return characters, settings
        except GoodreadsFetchError as err:
            last_error = err
            if not err.retryable or attempt >= retry_attempts:
                raise
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
    debug_simulated_error = options.get('debug_simulated_error', '')
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
            'title': book.get('title', _('Unknown Title')),
            'field_updates': {},
            'debug_characters': [],
            'debug_settings': {},
            'error': '',
        }
        try:
            simulation_error = simulated_goodreads_error(debug_simulated_error)
            if simulation_error is not None:
                raise simulation_error
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
