"""Transport integration with synthetic Goodreads pages and a deterministic clock."""

import json
import io
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from email.utils import formatdate

import test_smoke


def book_html(book_id=34, entities=True, title='A book'):
    book = {'title': title, 'legacyId': book_id}
    state = {'Book:example': book}
    if entities:
        state.update({
            'Character:one': {'__typename': 'Character', 'name': 'Alice', 'webUrl': '/characters/1'},
            'Places:one': {'__typename': 'Places', 'name': 'London', 'webUrl': '/places/1'},
        })
    return '<script id="__NEXT_DATA__" type="application/json">{}</script>'.format(
        json.dumps({'props': {'pageProps': {'apolloState': state}}}))


class Response(object):
    def __init__(self, status=200, html=None, final_url=None, headers=None):
        self.status = status
        self.headers = headers or {}
        self.raw = (book_html() if html is None else html).encode('utf-8')
        self.final_url = final_url
        self.read_called = False
        self.closed = False

    def geturl(self):
        return self.final_url

    def read(self):
        self.read_called = True
        return self.raw

    def close(self):
        self.closed = True


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_smoke.PluginSmokeTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.responses = []
        self.requests = []
        owner = self

        class Browser(object):
            def set_handle_robots(self, enabled):
                pass

            def open(self, url, timeout=None):
                owner.requests.append((url, owner.coordinator.clock()))
                response = owner.responses.pop(0)
                if isinstance(response, BaseException):
                    raise response
                response.final_url = response.final_url or url
                return response

        self.worker = self.fixture.load_worker_process(Browser)
        self.coordinator = self.worker.RequestCoordinator()
        self.logs = []
        self.coordinator.log = self.logs.append
        self.worker.common._AUTODELETE_RULES = []
        self.addCleanup(self.worker.common.reset_runtime_caches)
        jitter = patch.object(self.worker, 'retry_delay', lambda number, base: min(60, base * 2 ** (number - 1)))
        jitter.start()
        self.addCleanup(jitter.stop)

    def fetch(self, **kwargs):
        return self.worker.fetch_and_extract_goodreads_data('34', **kwargs)

    def test_xml_html_uses_real_entity_extraction(self):
        response = Response()
        self.responses = [response]
        self.assertEqual((['Alice'], ['London']), self.fetch())
        self.assertTrue(self.requests[0][0].endswith('/34.xml'))
        self.assertTrue(response.closed)

    def test_valid_empty_and_filtered_results_need_one_request(self):
        for html, rules in (
            (book_html(entities=False), []),
            (book_html(), [{'pattern': '*', 'mode': 'wildcard'}]),
        ):
            with self.subTest(rules=rules):
                self.requests.clear()
                self.responses = [Response(html=html)]
                self.worker.common._AUTODELETE_RULES = rules
                self.assertEqual(([], []), self.fetch())
                self.assertEqual(1, len(self.requests))

    def test_fallback_reasons_are_bounded_and_keep_one_direction(self):
        cases = [Response(status=code) for code in (202, 403, 204, 404, 410)]
        cases += [Response(html=''), Response(html='<script id="__NEXT_DATA__">bad json</script>'),
                  Response(html=book_html(35)), Response(html=book_html(None)),
                  Response(final_url='https://www.goodreads.com/book/show/35')]
        for first in cases:
            with self.subTest(status=first.status, html=first.raw[:45]):
                self.requests.clear()
                self.responses = [first, Response()]
                self.assertEqual((['Alice'], ['London']), self.fetch())
                self.assertEqual(['34.xml', '34'], [url.rsplit('/', 1)[-1] for url, _ in self.requests])
                if first.status in (202, 403):
                    self.assertGreaterEqual(self.requests[1][1] - self.requests[0][1], 60)

    def test_both_variants_bad_fail_without_more_attempts(self):
        for first in (202, 403, 404, 200):
            with self.subTest(status=first):
                self.requests.clear()
                self.responses = [Response(status=first, html=''), Response(status=first, html='')]
                with self.assertRaises(self.worker.GoodreadsFetchError):
                    self.fetch()
                self.assertEqual(2, len(self.requests))

    def test_redirect_to_same_book_is_accepted_but_other_destinations_fail(self):
        self.responses = [Response(final_url='https://www.goodreads.com/book/show/34.The_Book')]
        self.assertEqual((['Alice'], ['London']), self.fetch())
        for url in ('https://www.goodreads.com/user/sign_in', 'https://example.org/book/show/34',
                    'http://www.goodreads.com/book/show/34'):
            self.responses = [Response(final_url=url), Response(final_url=url)]
            with self.assertRaises(self.worker.GoodreadsPageDataError):
                self.fetch()

    def test_conflicting_book_entities_and_nonnumeric_ids_are_rejected(self):
        payload = {'props': {'pageProps': {'apolloState': {
            'Book:one': {'title': 'One', 'legacyId': 34},
            'Book:other': {'title': 'Other', 'legacyId': 35},
        }}}}
        common = self.worker.common
        self.assertFalse(common.goodreads_payload_has_book_data(payload, '34'))
        for invalid in (None, True, 34.0, '34x'):
            payload['props']['pageProps']['apolloState'] = {'Book:one': {'title': 'One', 'legacyId': invalid}}
            self.assertFalse(common.goodreads_payload_has_book_data(payload, '34'))

    def test_four_total_attempts_include_fallback(self):
        self.responses = [Response(status=503), Response(html=''), Response(status=500), Response()]
        self.assertEqual((['Alice'], ['London']), self.fetch(interval_seconds=1))
        self.assertEqual(['34.xml', '34.xml', '34', '34'], [url.rsplit('/', 1)[-1] for url, _ in self.requests])
        self.assertEqual([2, 4, 8], [self.requests[i + 1][1] - self.requests[i][1] for i in range(3)])
        self.requests.clear()
        self.responses = [Response(status=503) for _ in range(5)]
        with self.assertRaises(self.worker.GoodreadsHttpError):
            self.fetch()
        self.assertEqual(4, len(self.requests))
        self.assertEqual(1, len(self.responses))

    def test_terminal_errors_and_zero_retries(self):
        for error in (Response(status=401), Response(status=400), ValueError('bug')):
            self.requests.clear()
            self.responses = [error, Response()]
            with self.assertRaises((self.worker.GoodreadsFetchError, ValueError)):
                self.fetch()
            self.assertEqual(1, len(self.requests))
        self.requests.clear()
        self.responses = [Response(status=404)]
        with self.assertRaises(self.worker.GoodreadsHttpError):
            self.fetch(retry_attempts=0)
        self.assertEqual(1, len(self.requests))

    def test_network_timeout_retries_current_variant(self):
        self.responses = [URLError(TimeoutError('timeout')), Response()]
        self.assertEqual((['Alice'], ['London']), self.fetch())
        self.assertTrue(all(url.endswith('.xml') for url, _ in self.requests))

    def test_http_exception_and_header_only_challenge_preserve_metadata(self):
        error = HTTPError('https://www.goodreads.com/book/show/34.xml', 429, 'limited', {'Retry-After': '125'}, io.BytesIO(b''))
        self.responses = [error]
        with self.assertRaises(self.worker.GoodreadsHttpError) as caught:
            self.fetch(retry_attempts=0)
        self.assertEqual(125, caught.exception.retry_after_seconds)
        self.assertEqual(429, caught.exception.status_code)
        self.assertGreaterEqual(self.coordinator._load()['cooldown_until'], self.coordinator.clock() + 125)
        challenge = Response(headers={'X-Amzn-Waf-Action': 'challenge'})
        self.responses = [challenge, Response()]
        self.assertEqual((['Alice'], ['London']), self.fetch())
        self.assertFalse(challenge.read_called)
        self.assertTrue(challenge.closed)

    def test_failed_book_preserves_fields_then_next_book_waits_and_succeeds(self):
        self.responses = [Response(status=202), Response(status=403), Response(html=book_html(35, entities=False))]
        notifications = []
        results = self.worker.process_goodreads_batch(
            [{'book_id': 1, 'goodreads_id': '34'}, {'book_id': 2, 'goodreads_id': '35'}],
            {'query_interval_seconds': 1, 'write_empty_to_custom_fields': True,
             'field_specs': {'character_field': {'field_name': '#characters'}}},
            notification=lambda fraction, title: notifications.append(fraction),
        )
        self.assertTrue(results[0]['error'])
        self.assertEqual({}, results[0]['field_updates'])
        self.assertFalse(results[1]['error'])
        self.assertEqual([0.5, 1.0], notifications)
        self.assertGreaterEqual(self.requests[2][1] - self.requests[1][1], 60)

    def test_retry_after_takes_precedence_over_shorter_interval(self):
        self.responses = [Response(status=429, headers={'retry-after': '120'}), Response()]
        self.assertEqual((['Alice'], ['London']), self.fetch(interval_seconds=1))
        self.assertEqual(120, self.requests[1][1] - self.requests[0][1])

    def test_http_date_and_challenge_do_not_shorten_retry_after(self):
        date = formatdate(self.coordinator.clock() + 180, usegmt=True)
        self.responses = [Response(status=503, headers={'Retry-After': date}), Response()]
        self.assertEqual((['Alice'], ['London']), self.fetch(interval_seconds=1))
        self.assertEqual(180, self.requests[1][1] - self.requests[0][1])
        self.requests.clear()
        self.responses = [Response(status=429, headers={'Retry-After': '300', 'x-amzn-waf-action': 'challenge'}), Response()]
        self.assertEqual((['Alice'], ['London']), self.fetch(interval_seconds=1))
        self.assertEqual(300, self.requests[1][1] - self.requests[0][1])

    def test_retry_budget_exhausted_before_fallback_still_stops_at_four(self):
        self.responses = [Response(status=500) for _ in range(3)] + [Response(status=404), Response()]
        with self.assertRaises(self.worker.GoodreadsHttpError):
            self.fetch()
        self.assertEqual(4, len(self.requests))

    def test_coordination_failure_preserves_existing_fields_without_fetching(self):
        from calibre_plugins.Goodreads_character_and_settings.fetch_policy import FetchCoordinationError
        with patch.object(self.coordinator, '_load', side_effect=FetchCoordinationError('corrupt timing state')):
            results = self.worker.process_goodreads_batch(
                [{'book_id': 1, 'goodreads_id': '34', 'existing_fields': {'#characters': ['Kept']}}],
                {'write_empty_to_custom_fields': True, 'field_specs': {'character_field': {'field_name': '#characters'}}},
            )
        self.assertEqual([], self.requests)
        self.assertEqual({}, results[0]['field_updates'])
        self.assertIn('corrupt timing state', results[0]['error'])


if __name__ == '__main__':
    unittest.main()
