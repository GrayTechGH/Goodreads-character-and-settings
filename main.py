#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2026, GrayTechGH'
__docformat__ = 'restructuredtext en'

import json
import re
import time
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from qt.core import QMessageBox

from calibre_plugins.Goodreads_character_and_settings.config import prefs


GOODREADS_BASE_URL = 'https://www.goodreads.com'
GOODREADS_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
)


class GoodreadsPreviewRunner(object):

    def __init__(self, gui):
        self.gui = gui

    def run_for_selection(self):
        selected_books = self.get_selected_books()
        if not selected_books:
            QMessageBox.information(
                self.gui,
                'Goodreads character and settings',
                'Select at least one library book to test Goodreads extraction.',
            )
            return

        books_with_ids = [
            book for book in selected_books[:5]
            if book['goodreads_id']
        ]

        if not books_with_ids:
            QMessageBox.information(
                self.gui,
                'Goodreads character and settings',
                'None of the selected books has a Goodreads id.',
            )
            return

        interval_seconds = max(1, int(prefs['query_interval_seconds']))
        for index, book in enumerate(books_with_ids):
            if index:
                time.sleep(interval_seconds)

            try:
                html = fetch_goodreads_page(book['goodreads_id'])
                characters = extract_goodreads_values(html, 'Characters')
                settings = extract_goodreads_values(html, 'Setting')
                formatted_settings = format_settings(settings)
                body = build_preview_message(characters, formatted_settings)
            except Exception as err:
                body = 'Failed to fetch or parse Goodreads data.\n\n{}'.format(err)

            QMessageBox.information(
                self.gui,
                '{} by {}'.format(book['title'], book['author']),
                body,
            )

    def get_selected_books(self):
        library_view = getattr(self.gui, 'library_view', None)
        if library_view is None:
            return []

        selection_model = library_view.selectionModel()
        if selection_model is None:
            return []

        rows = selection_model.selectedRows()
        if not rows:
            return []

        model = library_view.model()
        db = self.gui.current_db
        books = []
        for row in rows:
            book_id = model.id(row)
            mi = db.get_metadata(book_id, index_is_id=True)
            identifiers = get_metadata_identifiers(mi)
            books.append({
                'title': mi.title or 'Unknown Title',
                'author': format_authors(getattr(mi, 'authors', None)),
                'goodreads_id': clean_goodreads_id(identifiers.get('goodreads')),
            })
        return books


def fetch_goodreads_page(goodreads_id, timeout=30):
    url = '{}/book/show/{}'.format(GOODREADS_BASE_URL, goodreads_id)
    request = Request(url, headers={'User-Agent': GOODREADS_USER_AGENT})
    try:
        response = urlopen(request, timeout=timeout)
        raw = response.read()
    except HTTPError as err:
        raise RuntimeError('HTTP error {} while fetching {}'.format(err.code, url))
    except URLError as err:
        raise RuntimeError('Network error while fetching {}: {}'.format(url, err))

    return raw.decode('utf-8', errors='replace')


def extract_goodreads_values(html, label):
    values = []

    values.extend(extract_values_from_json(label, html))
    values.extend(extract_values_from_html_block(label, html))

    deduped = []
    seen = set()
    for value in values:
        normalized = cleanup_value(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    return deduped


def extract_values_from_json(label, html):
    values = []
    for script_match in re.finditer(
        r'<script[^>]*type="application/ld\+json"[^>]*>(?P<body>.*?)</script>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        try:
            payload = json.loads(unescape(script_match.group('body')))
        except Exception:
            continue
        values.extend(find_label_values_in_json(payload, label.lower()))
    return values


def find_label_values_in_json(node, label):
    matches = []
    if isinstance(node, dict):
        lower_keys = {str(key).lower(): key for key in node}
        name_key = lower_keys.get('name')
        values_key = lower_keys.get('values')
        if name_key is not None and values_key is not None:
            name = cleanup_value(node.get(name_key))
            if name and name.lower() == label:
                matches.extend(flatten_json_values(node.get(values_key)))

        for value in node.values():
            matches.extend(find_label_values_in_json(value, label))
    elif isinstance(node, list):
        for value in node:
            matches.extend(find_label_values_in_json(value, label))
    return matches


def flatten_json_values(node):
    values = []
    if isinstance(node, list):
        for item in node:
            values.extend(flatten_json_values(item))
    elif isinstance(node, dict):
        for key in ('name', 'text', 'value'):
            if key in node:
                values.extend(flatten_json_values(node[key]))
    elif isinstance(node, str):
        values.append(node)
    return values


def extract_values_from_html_block(label, html):
    label_pattern = r'(?:>\s*{0}\s*<|"\s*{0}\s*"|>\s*{0}\s*:?\s*<)'.format(
        re.escape(label)
    )
    match = re.search(label_pattern, html, flags=re.IGNORECASE)
    if not match:
        return []

    block = html[match.start():match.start() + 4000]
    stop_match = re.search(
        r'(?:>\s*(?:Genres|Series|About the author|Lists with This Book|Book details & editions|Readers also enjoyed|Community Reviews)\s*<)',
        block,
        flags=re.IGNORECASE,
    )
    if stop_match:
        block = block[:stop_match.start()]

    values = []
    for anchor_match in re.finditer(r'<a\b[^>]*>(?P<text>.*?)</a>', block, flags=re.IGNORECASE | re.DOTALL):
        text = strip_tags(anchor_match.group('text'))
        if text and text.lower() != label.lower():
            values.append(text)

    if values:
        return values

    text = strip_tags(block)
    text = re.sub(r'\b{}\b'.format(re.escape(label)), '', text, flags=re.IGNORECASE)
    parts = [cleanup_value(part) for part in re.split(r'[\n|]+', text)]
    return [part for part in parts if part]


def format_settings(settings):
    if not settings:
        return []

    places = []
    countries = []
    seen_places = set()
    seen_countries = set()

    for value in settings:
        match = re.match(r'^(?P<place>.+?)\s*\((?P<country>.+?)\)$', value)
        if match:
            place = match.group('place').replace(', ', ' - ')
            country = cleanup_value(match.group('country'))
            if place and place not in seen_places:
                seen_places.add(place)
                places.append(place)
            if country and country not in seen_countries:
                seen_countries.add(country)
                countries.append(country)
            continue

        place = value.replace(', ', ' - ')
        if place and place not in seen_places:
            seen_places.add(place)
            places.append(place)

    combined = []
    if places:
        combined.append(' , '.join(places))
    if countries:
        combined.append(', '.join(countries))
    return [part for part in combined if part]


def build_preview_message(characters, settings):
    return 'Settings: {}\n\nCharacters: {}'.format(
        ', '.join(settings) if settings else 'Not found',
        ', '.join(characters) if characters else 'Not found',
    )


def get_metadata_identifiers(mi):
    getter = getattr(mi, 'get_identifiers', None)
    if callable(getter):
        return getter() or {}
    return getattr(mi, 'identifiers', {}) or {}


def clean_goodreads_id(value):
    if value is None:
        return None
    text = cleanup_value(value)
    if not text:
        return None
    match = re.search(r'(\d+)', text)
    return match.group(1) if match else None


def format_authors(authors):
    if not authors:
        return 'Unknown Author'
    return ' & '.join(authors)


def cleanup_value(value):
    if value is None:
        return ''
    if not isinstance(value, str):
        value = str(value)
    value = strip_tags(unescape(value))
    value = value.replace('\xa0', ' ')
    value = re.sub(r'\s+', ' ', value)
    return value.strip(' ,;:-')


def strip_tags(text):
    return re.sub(r'<[^>]+>', ' ', text or '')
