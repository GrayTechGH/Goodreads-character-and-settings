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
from urllib.error import URLError

from calibre import browser

from calibre_plugins.Goodreads_character_and_settings import common
from calibre_plugins.Goodreads_character_and_settings.fetch_policy import (
    RequestCoordinator, parse_retry_after, retry_delay,
)


GOODREADS_BASE_URL = 'https://www.goodreads.com'
GOODREADS_WAF_CHALLENGE_MESSAGE = _(
    'Goodreads is requiring a browser challenge and returned no usable book page.'
)
GOODREADS_MISSING_BOOK_DATA_MESSAGE = _(
    'Goodreads returned a 200 response without usable book data.'
)
GOODREADS_HTTP_ERROR_MESSAGES = {
    204: _('Goodreads returned no content for this book page.'),
    401: _('Goodreads requires sign-in to access this book page.'),
    403: _('Goodreads denied access to this book page.'),
    404: _('Goodreads could not find this book page.'),
    408: _('Goodreads timed out while handling this request.'),
    410: _('This Goodreads book page is no longer available.'),
    429: _('Goodreads is temporarily rate-limiting requests.'),
}
RETRYABLE_HTTP_STATUS_CODES = frozenset((408, 429, 500, 502, 503, 504))


class GoodreadsFetchError(RuntimeError):

    def __init__(self, message, retryable=False, status_code=None, retry_after_seconds=0, cooldown_seconds=0):
        RuntimeError.__init__(self, message)
        self.retryable = retryable
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
        self.cooldown_seconds = cooldown_seconds


class GoodreadsWafChallengeError(GoodreadsFetchError):
    pass


class GoodreadsHttpError(GoodreadsFetchError):

    def __init__(self, status_code, message, retryable=False, **kwargs):
        GoodreadsFetchError.__init__(self, message, retryable=retryable, status_code=status_code, **kwargs)


class GoodreadsPageDataError(GoodreadsFetchError):
    pass


class GoodreadsNetworkError(GoodreadsFetchError):
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
        value = get(name, '')
        if value:
            return str(value)
        for key, value in headers.items():
            if key.lower() == name.lower():
                return str(value or '')
    return ''


def is_goodreads_waf_challenge(response):
    if response_status_code(response) == 202:
        return True
    return 'challenge' in response_header(response, 'x-amzn-waf-action').lower()


def goodreads_response_error(response, now=None, retry_wait=2):
    status_code = response_status_code(response)
    server_delay = (
        parse_retry_after(response_header(response, 'Retry-After'), now)
        if status_code in (429, 503) else 0
    )
    if is_goodreads_waf_challenge(response):
        return GoodreadsWafChallengeError(
            GOODREADS_WAF_CHALLENGE_MESSAGE, status_code=status_code,
            retry_after_seconds=server_delay, cooldown_seconds=max(60, server_delay),
        )
    if status_code == 200:
        return None
    if status_code is None:
        return None  # Non-HTTP exceptions are classified by the transport below.

    message = GOODREADS_HTTP_ERROR_MESSAGES.get(status_code)
    if message is None and 500 <= status_code <= 599:
        message = _('Goodreads is temporarily unavailable (HTTP {}).').format(status_code)
    elif message is None:
        message = _('Goodreads returned an unusable response (HTTP {}).').format(status_code)
    if status_code == 403:
        cooldown = 60
    elif status_code in (429, 503):
        cooldown = max(server_delay, retry_wait)
    else:
        cooldown = 0
    return GoodreadsHttpError(
        status_code,
        message,
        retryable=status_code in RETRYABLE_HTTP_STATUS_CODES,
        retry_after_seconds=server_delay,
        cooldown_seconds=cooldown,
    )


def random_goodreads_user_agent():
    from calibre.utils.random_ua import random_common_chrome_user_agent
    return random_common_chrome_user_agent()


def goodreads_detail_url(goodreads_id, variant='xml'):
    if variant not in ('xml', 'plain'):
        raise ValueError(_('Unknown Goodreads detail URL variant.'))
    if not str(goodreads_id).isascii() or not str(goodreads_id).isdigit() or int(goodreads_id) <= 0:
        raise GoodreadsPageDataError(_('Invalid Goodreads book identifier.'))
    return '{}/book/show/{}{}'.format(GOODREADS_BASE_URL, goodreads_id, '.xml' if variant == 'xml' else '')


def fetch_goodreads_page(goodreads_id, timeout=30, variant='xml', coordinator=None,
                        interval_seconds=30, not_before=0, retry_wait=2):
    coordinator = coordinator if coordinator is not None else RequestCoordinator()
    url = goodreads_detail_url(goodreads_id, variant)
    return coordinator.run(
        lambda: _fetch_goodreads_response(url, timeout, coordinator.clock, retry_wait),
        interval_seconds=interval_seconds, not_before=not_before,
    )


def _fetch_goodreads_response(url, timeout, clock, retry_wait):
    response = None
    try:
        br = browser()
        br.set_handle_robots(False)
        br.addheaders = [('User-Agent', random_goodreads_user_agent())]
        response = br.open(url, timeout=timeout)
        response_error = goodreads_response_error(response, clock(), retry_wait)
        if response_error is not None:
            raise response_error
        if response_status_code(response) != 200:
            raise GoodreadsPageDataError(_('Goodreads returned a response without an HTTP status.'))
        final_url = response.geturl()
        raw = response.read()
    except GoodreadsFetchError:
        raise
    except Exception as err:
        response_error = goodreads_response_error(err, clock(), retry_wait)
        if response_error is not None:
            response = err
            raise response_error
        if isinstance(err, (URLError, TimeoutError, ConnectionError)):
            raise GoodreadsNetworkError(_('Error while fetching {}: {}').format(url, err), retryable=True) from err
        raise
    finally:
        close = getattr(response, 'close', None)
        if callable(close):
            close()

    return {'html': raw.decode('utf-8', errors='replace'), 'requested_url': url, 'final_url': final_url}


def should_retry_fetch(error):
    return isinstance(error, GoodreadsFetchError) and error.retryable


def should_fallback_fetch(error):
    return (
        isinstance(error, (GoodreadsWafChallengeError, GoodreadsPageDataError))
        or isinstance(error, GoodreadsHttpError) and error.status_code in (204, 403, 404, 410)
    )


def fetch_and_extract_goodreads_data(goodreads_id, retry_attempts=3, retry_delay_seconds=2,
                                    coordinator=None, interval_seconds=30, log=None):
    coordinator = coordinator if coordinator is not None else RequestCoordinator()
    log = log or coordinator.log
    variant = 'xml'
    not_before = 0
    total_attempts = max(0, int(retry_attempts)) + 1

    for attempt in range(total_attempts):
        label = 'attempt {}/{} ({})'.format(attempt + 1, total_attempts, variant)
        log('{} {}'.format(label, goodreads_detail_url(goodreads_id, variant)))
        delay = retry_delay(attempt + 1, base=retry_delay_seconds)
        try:
            page = fetch_goodreads_page(
                goodreads_id, variant=variant, coordinator=coordinator,
                interval_seconds=interval_seconds, not_before=not_before, retry_wait=delay,
            )
            html = page['html']
            if not common.goodreads_book_url_matches_id(page['final_url'], goodreads_id):
                raise GoodreadsPageDataError(_('Goodreads redirected to a different or unidentified book page.'), status_code=200)
            if not common.has_goodreads_book_data(html):
                raise GoodreadsPageDataError(GOODREADS_MISSING_BOOK_DATA_MESSAGE, status_code=200)
            if not common.has_goodreads_book_data(html, goodreads_id):
                raise GoodreadsPageDataError(_('Goodreads returned missing or conflicting book identity.'), status_code=200)
            characters = common.extract_goodreads_values(html, 'Characters')
            settings = common.extract_goodreads_values(html, 'Setting')
            log('{}: usable book data; {} characters, {} settings'.format(label, len(characters), len(settings)))
            return characters, settings
        except GoodreadsFetchError as err:
            log('{}: {}'.format(label, err))
            fallback = should_fallback_fetch(err)
            if (
                attempt + 1 == total_attempts
                or (fallback and variant == 'plain')
                or (not fallback and not should_retry_fetch(err))
            ):
                raise
            if fallback:
                variant = 'plain'
                log('falling back to extensionless URL: {}'.format(err))
            not_before = coordinator.clock() + max(delay, err.retry_after_seconds, err.cooldown_seconds)
        except Exception as err:
            log('{}: terminal {}'.format(label, type(err).__name__))
            raise


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
    retry_attempts = max(0, int(options.get('retry_attempts', 3)))
    retry_delay_seconds = max(1, int(options.get('retry_delay_seconds', 2)))
    results = []
    total = max(1, len(books))

    for index, book in enumerate(books):
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
                interval_seconds=interval_seconds,
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
