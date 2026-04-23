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

from calibre_plugins.Goodreads_character_and_settings.config import FIELD_NONE, FIELD_TAGS, prefs


GOODREADS_BASE_URL = 'https://www.goodreads.com'
GOODREADS_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
)
_SKIP_WRITE = object()


class GoodreadsPreviewRunner(object):

    def __init__(self, gui):
        self.gui = gui

    def run_for_selection(self):
        selected_books = self.get_selected_books()
        if not selected_books:
            self.show_status('No books selected.')
            return

        max_books_per_job = max(1, int(prefs['max_books_per_job']))
        books_with_ids = [
            book for book in selected_books[:max_books_per_job]
            if book['goodreads_id']
        ]

        if not books_with_ids:
            self.show_status('No selected books have a Goodreads id.')
            return

        interval_seconds = max(1, int(prefs['query_interval_seconds']))
        updated_count = 0
        failed_count = 0
        for index, book in enumerate(books_with_ids):
            if index:
                time.sleep(interval_seconds)

            try:
                html = fetch_goodreads_page(book['goodreads_id'])
                characters = extract_goodreads_values(html, 'Characters')
                settings = extract_goodreads_values(html, 'Setting')
                formatted_settings, countries = format_settings(
                    settings,
                    include_country_with_location=prefs['include_country_with_location'],
                )
                self.update_book_fields(
                    book,
                    characters,
                    formatted_settings,
                    countries,
                )
                updated_count += 1
            except Exception:
                failed_count += 1

        self.refresh_gui(updated_count)
        self.show_status(
            'Goodreads character and settings updated {} book(s); {} failed.'.format(
                updated_count,
                failed_count,
            )
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
                'book_id': book_id,
                'title': mi.title or 'Unknown Title',
                'author': format_authors(getattr(mi, 'authors', None)),
                'goodreads_id': clean_goodreads_id(identifiers.get('goodreads')),
            })
        return books

    def update_book_fields(self, book, characters, settings, countries):
        db = self.gui.current_db
        book_id = book['book_id']

        assignments = [
            ('character_field', characters),
            ('settings_field', settings),
            ('countries_field', countries),
        ]

        for pref_name, values in assignments:
            self.write_field_value(db, book_id, prefs[pref_name], values)

    def write_field_value(self, db, book_id, field_name, values):
        if field_name == FIELD_NONE:
            return

        existing_values = self.get_existing_field_values(db, book_id, field_name)

        if field_name == FIELD_TAGS:
            payload = merge_unique_values(existing_values, values)
            if not payload:
                return
        else:
            payload = self.prepare_custom_field_value(
                db,
                field_name,
                existing_values,
                values,
            )
            if payload is _SKIP_WRITE:
                return

        new_api = getattr(db, 'new_api', None)
        if new_api is not None and hasattr(new_api, 'set_field'):
            new_api.set_field(field_name, {book_id: payload})
            return

        mi = db.get_metadata(book_id, index_is_id=True)
        setter = getattr(mi, 'set', None)
        if callable(setter):
            setter(field_name, payload)
        else:
            setattr(mi, field_name, payload)
        db.set_metadata(book_id, mi, set_title=False, set_authors=False, commit=True)

    def get_existing_field_values(self, db, book_id, field_name):
        mi = db.get_metadata(book_id, index_is_id=True)
        if field_name == FIELD_TAGS:
            return list(getattr(mi, 'tags', None) or [])

        getter = getattr(mi, 'get', None)
        if callable(getter):
            current_value = getter(field_name)
        else:
            current_value = getattr(mi, field_name, None)
        return normalize_field_values(current_value)

    def prepare_custom_field_value(self, db, field_name, existing_values, values):
        if values:
            metadata = getattr(db, 'field_metadata', {}).get(field_name, {})
            is_multiple = metadata.get('is_multiple')
            merged_values = merge_unique_values(existing_values, values)
            if is_multiple:
                return merged_values
            return ', '.join(merged_values)

        if prefs['write_empty_to_custom_fields']:
            metadata = getattr(db, 'field_metadata', {}).get(field_name, {})
            is_multiple = metadata.get('is_multiple')
            merged_values = merge_unique_values(existing_values, ['Empty'])
            if is_multiple:
                return merged_values
            return ', '.join(merged_values)
        return _SKIP_WRITE

    def refresh_gui(self, updated_count):
        if not updated_count:
            return
        model = getattr(getattr(self.gui, 'library_view', None), 'model', lambda: None)()
        if model is not None and hasattr(model, 'refresh_ids'):
            model.refresh_ids([])
        elif model is not None and hasattr(model, 'refresh'):
            model.refresh()
        tags_view = getattr(self.gui, 'tags_view', None)
        if tags_view is not None and hasattr(tags_view, 'recount'):
            tags_view.recount()

    def show_status(self, message, timeout=5000):
        status_bar = getattr(self.gui, 'status_bar', None)
        if status_bar is not None and hasattr(status_bar, 'show_message'):
            status_bar.show_message(message, timeout)


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


def normalize_field_values(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        normalized = []
        for item in value:
            cleaned = cleanup_value(item)
            if cleaned:
                normalized.append(cleaned)
        return normalized
    if isinstance(value, str):
        parts = [cleanup_value(part) for part in value.split(',')]
        return [part for part in parts if part]

    cleaned = cleanup_value(value)
    return [cleaned] if cleaned else []


def merge_unique_values(existing_values, new_values):
    merged = []
    seen = set()
    for source in (existing_values or [], new_values or []):
        for value in source:
            cleaned = cleanup_value(value)
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                merged.append(cleaned)
    return merged


def extract_goodreads_values(html, label):
    values = []
    labels = expand_label_aliases(label)

    for candidate in labels:
        values.extend(extract_values_from_json(candidate, html))
        values.extend(extract_values_from_embedded_state(candidate, html))
        values.extend(extract_values_from_detail_section(candidate, html))
        values.extend(extract_values_from_html_block(candidate, html))

    deduped = []
    seen = set()
    for value in values:
        for normalized in normalize_extracted_value(value):
            if normalized and normalized not in seen:
                seen.add(normalized)
                deduped.append(normalized)
    return deduped


def expand_label_aliases(label):
    aliases = [label]
    lower_label = label.lower()

    if lower_label == 'setting':
        aliases.extend(['Settings', 'Places'])
    elif lower_label == 'characters':
        aliases.append('Character')

    deduped = []
    seen = set()
    for value in aliases:
        normalized = value.lower()
        if normalized not in seen:
            seen.add(normalized)
            deduped.append(value)
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


def extract_values_from_embedded_state(label, html):
    values = []
    for candidate_html in iter_embedded_state_variants(html):
        key_names = [label.lower()]
        if label.lower() == 'characters':
            key_names.append('characters')
        elif label.lower() in ('setting', 'settings', 'places'):
            key_names.append('places')

        for key_name in key_names:
            values.extend(extract_keyed_values_from_embedded_state(candidate_html, key_name))

        pattern = r'"name"\s*:\s*"{0}"'.format(re.escape(label))
        for match in re.finditer(pattern, candidate_html, flags=re.IGNORECASE):
            tail = candidate_html[match.end():match.end() + 12000]
            raw_values = extract_values_payload_from_tail(tail)
            if raw_values is not None:
                values.extend(flatten_json_values(raw_values))
    return values


def iter_embedded_state_variants(html):
    variants = []
    candidates = [
        html,
        unescape(html),
        html.replace('\\"', '"'),
        unescape(html).replace('\\"', '"'),
    ]
    seen = set()
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            variants.append(candidate)
    return variants


def extract_values_payload_from_tail(tail):
    string_match = re.search(
        r'"values"\s*:\s*"(?P<value>(?:\\.|[^"])*)"',
        tail,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if string_match:
        raw_value = string_match.group('value')
        return try_parse_json_string('"{}"'.format(raw_value))

    direct_match = re.search(
        r'"values"\s*:\s*(?P<value>\[.*?\]|\{.*?\})',
        tail,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if direct_match:
        raw_value = direct_match.group('value')
        return try_parse_json_string(raw_value)

    return None


def extract_keyed_values_from_embedded_state(html, key_name):
    values = []
    pattern = r'"{0}"\s*:'.format(re.escape(key_name))
    for match in re.finditer(pattern, html, flags=re.IGNORECASE):
        tail = html[match.end():]
        raw_values, consumed = extract_bracketed_json_payload(tail)
        if raw_values is None:
            continue
        values.extend(flatten_json_values(raw_values))
        if consumed:
            tail = tail[consumed:]
    return values


def extract_bracketed_json_payload(text):
    start = None
    opening = ''
    for index, char in enumerate(text):
        if char in '[{':
            start = index
            opening = char
            break
        if char not in ' \t\r\n:':
            return None, 0
    if start is None:
        return None, 0

    closing = ']' if opening == '[' else '}'
    depth = 0
    in_string = False
    escape = False

    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == '\\':
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                payload = text[start:index + 1]
                return try_parse_json_string(payload), index + 1

    return None, 0


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
        formatted = format_json_value_object(node)
        if formatted:
            values.append(formatted)
        else:
            for key in ('name', 'text', 'value'):
                if key in node:
                    values.extend(flatten_json_values(node[key]))
    elif isinstance(node, str):
        parsed = try_parse_json_string(node)
        if parsed is not None:
            values.extend(flatten_json_values(parsed))
        else:
            values.append(node)
    return values


def format_json_value_object(node):
    if not isinstance(node, dict):
        return ''

    name = cleanup_value(node.get('name'))
    country = cleanup_value(node.get('countryName'))

    if name and country:
        return '{} ({})'.format(name, country)
    if name:
        return name

    for key in ('text', 'value'):
        value = cleanup_value(node.get(key))
        if value:
            return value
    return ''


def normalize_extracted_value(value):
    parsed = try_parse_json_string(value) if isinstance(value, str) else None
    if parsed is not None:
        normalized = []
        for item in flatten_json_values(parsed):
            cleaned = cleanup_value(item)
            if cleaned:
                normalized.append(cleaned)
        return normalized

    cleaned = cleanup_value(value)
    return [cleaned] if cleaned else []


def extract_values_from_detail_section(label, html):
    label_match = re.search(
        r'>\s*{}\s*<'.format(re.escape(label)),
        html,
        flags=re.IGNORECASE,
    )
    if not label_match:
        return []

    tail = html[label_match.end():label_match.end() + 12000]
    stop_labels = [
        'Characters', 'Setting', 'Literary awards', 'Awards', 'Places',
        'Book details & editions', 'This edition', 'Lists with This Book',
        'Readers also enjoyed', 'Community Reviews', 'Genres',
    ]
    stop_patterns = [
        r'>\s*{}\s*<'.format(re.escape(stop_label))
        for stop_label in stop_labels
        if stop_label.lower() != label.lower()
    ]
    stop_match = re.search('|'.join(stop_patterns), tail, flags=re.IGNORECASE)
    if stop_match:
        tail = tail[:stop_match.start()]

    values = []
    for anchor_match in re.finditer(
        r'<a\b[^>]*>(?P<text>.*?)</a>',
        tail,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        text = cleanup_value(anchor_match.group('text'))
        if not text:
            continue
        if text.lower() in ('show more', 'show less'):
            continue
        values.append(text)
    return values


def extract_values_from_html_block(label, html):
    label_pattern = r'(?:>\s*{0}\s*<|>\s*{0}\s*:?\s*<)'.format(
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


def format_settings(settings, include_country_with_location=True):
    if not settings:
        return [], []

    places = []
    countries = []
    seen_places = set()
    seen_countries = set()

    for value in settings:
        match = re.match(r'^(?P<place>.+?)\s*\((?P<country>.+?)\)$', value)
        if match:
            place_name = match.group('place').replace(', ', ' - ')
            country = cleanup_value(match.group('country'))
            place = place_name
            if include_country_with_location and country:
                place = '{} ({})'.format(place_name, country)
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

    formatted_places = [' , '.join(places)] if places else []
    formatted_countries = [', '.join(countries)] if countries else []
    return formatted_places, formatted_countries


def build_preview_message(characters, settings, countries):
    return 'Settings: {}\nCountries: {}\n\nCharacters: {}'.format(
        ', '.join(settings) if settings else 'Not found',
        ', '.join(countries) if countries else 'Not found',
        ', '.join(characters) if characters else 'Not found',
    )


def build_debug_message(html):
    labels = ('Characters', 'Setting', 'Settings', 'Places')
    lines = ['Debug:']

    for label in labels:
        json_values = extract_values_from_json(label, html)
        state_values = extract_values_from_embedded_state(label, html)
        detail_values = extract_values_from_detail_section(label, html)
        html_values = extract_values_from_html_block(label, html)
        marker_found = has_label_marker(html, label)
        json_count = len(extract_normalized_values(json_values))
        state_count = len(extract_normalized_values(state_values))
        detail_count = len(extract_normalized_values(detail_values))
        html_count = len(extract_normalized_values(html_values))
        lines.append(
            '{}: markers={} json={} state={} detail={} html={}'.format(
                label,
                'yes' if marker_found else 'no',
                json_count,
                state_count,
                detail_count,
                html_count,
            )
        )
        if marker_found and not any((json_count, state_count, detail_count, html_count)):
            snippet = extract_marker_snippet(html, label)
            if snippet:
                lines.append('  snippet={}'.format(snippet))

    return '\n'.join(lines)


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


def has_label_marker(html, label):
    return bool(
        re.search(r'>\s*{}\s*<'.format(re.escape(label)), html, flags=re.IGNORECASE)
        or re.search(r'"\s*{}\s*"'.format(re.escape(label)), html, flags=re.IGNORECASE)
    )


def extract_normalized_values(values):
    normalized = []
    for value in values:
        normalized.extend(normalize_extracted_value(value))
    return normalized


def extract_marker_snippet(html, label, radius=180):
    patterns = [
        r'>\s*{}\s*<'.format(re.escape(label)),
        r'"\s*{}\s*"'.format(re.escape(label)),
    ]
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if not match:
            continue
        start = max(0, match.start() - radius)
        end = min(len(html), match.end() + radius)
        snippet = html[start:end]
        snippet = snippet.replace('\n', ' ').replace('\r', ' ')
        snippet = re.sub(r'\s+', ' ', snippet)
        return snippet[:240]
    return ''


def strip_tags(text):
    return re.sub(r'<[^>]+>', ' ', text or '')


def try_parse_json_string(value):
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None

    current = text
    for _ in range(3):
        stripped = current.strip()
        if not stripped:
            return None
        if stripped[0] not in '[{"':
            return None
        try:
            parsed = json.loads(stripped)
        except Exception:
            return None
        if not isinstance(parsed, str):
            return parsed
        current = unescape(parsed)
    return None
