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

import json
import os
import re
import sys
from fnmatch import fnmatchcase
from html import unescape

from calibre_plugins.Goodreads_character_and_settings.settings_data import (
    active_language_code,
    ensure_user_json_files,
    load_user_autodelete_values,
    load_user_country_data,
    load_user_region_data,
    plugin_data_dir,
    read_bundled_plugin_ui_translations,
)


FIELD_NONE = 'none'
_SKIP_WRITE = object()
_LAST_EXTRACTION_DEBUG = {}
_COUNTRY_VARIANT_LOOKUP = None
_COUNTRY_VARIANT_PATTERNS = None
_COUNTRY_VARIANT_SOURCE = ''
_AUTODELETE_VALUES = None
_AUTODELETE_PATTERNS = None
_PLUGIN_UI_TRANSLATIONS = None
_PLUGIN_UI_TRANSLATION_DEBUG_MESSAGES = set()


def reset_runtime_caches():
    global _COUNTRY_VARIANT_LOOKUP, _COUNTRY_VARIANT_PATTERNS, _COUNTRY_VARIANT_SOURCE, _AUTODELETE_VALUES, _AUTODELETE_PATTERNS
    _COUNTRY_VARIANT_LOOKUP = None
    _COUNTRY_VARIANT_PATTERNS = None
    _COUNTRY_VARIANT_SOURCE = ''
    _AUTODELETE_VALUES = None
    _AUTODELETE_PATTERNS = None
    _PLUGIN_UI_TRANSLATION_DEBUG_MESSAGES.clear()


def plugin_ui_translations():
    global _PLUGIN_UI_TRANSLATIONS
    if _PLUGIN_UI_TRANSLATIONS is not None:
        return _PLUGIN_UI_TRANSLATIONS
    try:
        payload = read_bundled_plugin_ui_translations()
        translations = payload.get('translations', {}) if isinstance(payload, dict) else {}
        _PLUGIN_UI_TRANSLATIONS = translations if isinstance(translations, dict) else {}
    except Exception:
        _PLUGIN_UI_TRANSLATIONS = {}
    return _PLUGIN_UI_TRANSLATIONS


def plugin_ui_text(text, native_translate=None):
    if callable(native_translate):
        translated = native_translate(text)
        if translated != text:
            return translated
    language = active_language_code()
    translations = plugin_ui_translations()
    language_translations = translations.get(language)
    if not language_translations:
        base_language = language.split('_', 1)[0]
        language_translations = translations.get(base_language, {})
        if not language_translations:
            log_plugin_ui_translation_debug(
                'missing_language:{}'.format(language),
                'Goodreads character and settings: no plugin UI translations for language {!r}'.format(language),
            )
            return text
    if text not in language_translations:
        log_plugin_ui_translation_debug(
            'missing_text:{}:{}'.format(language, text),
            'Goodreads character and settings: no plugin UI translation for {!r} in language {!r}'.format(
                text,
                language,
            ),
        )
    return language_translations.get(text, text)


def log_plugin_ui_translation_debug(key, message):
    if not is_running_under_calibre_debug():
        return
    if key in _PLUGIN_UI_TRANSLATION_DEBUG_MESSAGES:
        return
    _PLUGIN_UI_TRANSLATION_DEBUG_MESSAGES.add(key)
    print(message, flush=True)


def is_running_under_calibre_debug():
    candidates = [sys.argv[0], sys.executable] + list(sys.argv[1:])
    for candidate in candidates:
        executable = os.path.basename(str(candidate or '')).lower()
        if executable in ('calibre-debug', 'calibre-debug.exe'):
            return True
    try:
        from calibre.constants import DEBUG
        return bool(DEBUG)
    except Exception:
        return False


def debug_pref(name):
    try:
        from calibre_plugins.Goodreads_character_and_settings.config import prefs
        return prefs.get(name)
    except Exception:
        return False


def merge_unique_values(existing_values, new_values):
    merged = []
    seen = set()
    for source in (existing_values or [], new_values or []):
        for value in source:
            cleaned = cleanup_value(value)
            lookup_key = cleaned.casefold()
            if cleaned and lookup_key not in seen:
                seen.add(lookup_key)
                merged.append(cleaned)
    return merged


def normalize_values_for_field(values, spec):
    normalized = []
    seen = set()
    for value in values or []:
        cleaned = cleanup_value(value)
        if not cleaned:
            continue
        lookup_key = cleaned.casefold()
        if lookup_key in seen:
            continue
        seen.add(lookup_key)
        normalized.append(cleaned)

    if spec.get('is_tags') or spec.get('is_multiple'):
        normalized.sort(key=lambda item: item.casefold())
    return normalized


def load_country_variant_data():
    global _COUNTRY_VARIANT_LOOKUP, _COUNTRY_VARIANT_PATTERNS, _COUNTRY_VARIANT_SOURCE
    if _COUNTRY_VARIANT_LOOKUP is not None and _COUNTRY_VARIANT_PATTERNS is not None:
        return _COUNTRY_VARIANT_LOOKUP, _COUNTRY_VARIANT_PATTERNS

    lookup = {}
    patterns = []
    try:
        ensure_user_json_files()
        countries = load_user_country_data()
        regions = load_user_region_data()
        _COUNTRY_VARIANT_SOURCE = plugin_data_dir()
    except Exception as err:
        _COUNTRY_VARIANT_LOOKUP = {}
        _COUNTRY_VARIANT_PATTERNS = []
        _COUNTRY_VARIANT_SOURCE = 'unavailable: {}'.format(err)
        print(
            'Goodreads character and settings: failed to load user country data: {}'.format(
                _COUNTRY_VARIANT_SOURCE
            ),
            flush=True,
        )
        return _COUNTRY_VARIANT_LOOKUP, _COUNTRY_VARIANT_PATTERNS

    seen_variants = set()
    for item in countries:
        canonical_country = item.get('country', '')
        normalized_variants = collect_country_variants(
            canonical_country,
            {'replace_in_settings': item.get('aliases', []), 'keep_in_settings': []},
        )
        for variant, keep_in_settings in normalized_variants:
            cleaned_variant = cleanup_country_variant(variant)
            if not cleaned_variant:
                continue
            lowered = cleaned_variant.lower()
            lookup[lowered] = {
                'canonical_country': canonical_country,
                'keep_in_settings': keep_in_settings,
                'variant': cleaned_variant,
            }
            if lowered not in seen_variants:
                seen_variants.add(lowered)
                patterns.append((cleaned_variant, canonical_country, keep_in_settings))

    for item in regions:
        canonical_country = item.get('country', '')
        normalized_variants = collect_country_variants(
            canonical_country,
            {'replace_in_settings': [], 'keep_in_settings': [item.get('region', '')]},
        )
        for variant, keep_in_settings in normalized_variants:
            cleaned_variant = cleanup_country_variant(variant)
            if not cleaned_variant:
                continue
            lowered = cleaned_variant.lower()
            lookup[lowered] = {
                'canonical_country': canonical_country,
                'keep_in_settings': keep_in_settings,
                'variant': cleaned_variant,
            }
            if lowered not in seen_variants:
                seen_variants.add(lowered)
                patterns.append((cleaned_variant, canonical_country, keep_in_settings))

    patterns.sort(key=lambda item: len(item[0]), reverse=True)
    _COUNTRY_VARIANT_LOOKUP = lookup
    _COUNTRY_VARIANT_PATTERNS = patterns
    return _COUNTRY_VARIANT_LOOKUP, _COUNTRY_VARIANT_PATTERNS


def load_autodelete_values():
    global _AUTODELETE_VALUES, _AUTODELETE_PATTERNS
    if _AUTODELETE_VALUES is not None and _AUTODELETE_PATTERNS is not None:
        return _AUTODELETE_VALUES, _AUTODELETE_PATTERNS
    try:
        ensure_user_json_files()
        exact_values = set()
        wildcard_patterns = []
        for value in load_user_autodelete_values():
            cleaned = cleanup_value(value)
            if not cleaned:
                continue
            lowered = cleaned.casefold()
            if '*' in lowered:
                wildcard_patterns.append(lowered)
            else:
                exact_values.add(lowered)
        _AUTODELETE_VALUES = exact_values
        _AUTODELETE_PATTERNS = wildcard_patterns
    except Exception as err:
        print(
            'Goodreads character and settings: failed to load autodelete values: {}'.format(
                err
            ),
            flush=True,
        )
        _AUTODELETE_VALUES = set()
        _AUTODELETE_PATTERNS = []
    return _AUTODELETE_VALUES, _AUTODELETE_PATTERNS


def should_autodelete_value(value, exact_values=None, wildcard_patterns=None):
    cleaned = cleanup_value(value)
    if not cleaned:
        return False
    lowered = cleaned.casefold()
    if exact_values is None or wildcard_patterns is None:
        exact_values, wildcard_patterns = load_autodelete_values()
    if lowered in exact_values:
        return True
    return any(fnmatchcase(lowered, pattern) for pattern in wildcard_patterns)


def collect_country_variants(canonical_country, variants):
    collected = [(canonical_country, False)]
    if isinstance(variants, dict):
        for variant in variants.get('replace_in_settings', []) or []:
            collected.append((variant, False))
        for variant in variants.get('keep_in_settings', []) or []:
            collected.append((variant, True))
        return collected

    for variant in variants or []:
        collected.append((variant, False))
    return collected


def cleanup_country_variant(value):
    text = cleanup_value(value)
    text = re.sub(r'\s+', ' ', text)
    return text.strip(' ,;:-')


def split_setting_value(value):
    cleaned_value = cleanup_value(value)
    if not cleaned_value:
        return '', '', ''

    match = re.match(r'^(?P<place>.*)\s*\((?P<country>[^()]*)\)\s*$', cleaned_value)
    if match:
        place = cleanup_value(match.group('place'))
        country = cleanup_country_variant(match.group('country'))
        country_match = canonicalize_country_name(country)
        if country_match:
            display_country = country if country_match['keep_in_settings'] else ''
            return place, display_country, country_match['canonical_country']

    matched_country, canonical_country, place, keep_in_settings = match_country_suffix(cleaned_value)
    if canonical_country:
        display_country = matched_country if keep_in_settings else ''
        return place, display_country, canonical_country

    return cleaned_value, '', ''


def canonicalize_country_name(value):
    lookup, _patterns = load_country_variant_data()
    cleaned_value = cleanup_country_variant(value)
    if not cleaned_value:
        return None
    return lookup.get(cleaned_value.lower())


def match_country_suffix(value):
    _lookup, patterns = load_country_variant_data()
    normalized_value = cleanup_country_variant(value)
    lowered_value = normalized_value.lower()

    for variant, canonical_country, keep_in_settings in patterns:
        lowered_variant = variant.lower()
        if lowered_value == lowered_variant:
            return variant, canonical_country, '', keep_in_settings
        if lowered_value.endswith(' ' + lowered_variant):
            place = cleanup_value(normalized_value[:-len(variant)])
            return variant, canonical_country, cleanup_setting_place(place), keep_in_settings
        if lowered_value.endswith(', ' + lowered_variant):
            place = cleanup_value(normalized_value[:-len(variant)])
            return variant, canonical_country, cleanup_setting_place(place), keep_in_settings
        if lowered_value.endswith(' - ' + lowered_variant):
            place = cleanup_value(normalized_value[:-len(variant)])
            return variant, canonical_country, cleanup_setting_place(place), keep_in_settings

    return '', '', '', False


def cleanup_setting_place(value):
    place = cleanup_value(value)
    while True:
        match = re.search(r'\s*\(([^()]*)\)\s*$', place)
        if not match:
            break
        inner = match.group(1).strip()
        if inner and any(char.isalpha() for char in inner):
            break
        place = place[:match.start()]
    place = re.sub(r'[\s,;\-]+$', '', place)
    return place.replace(', ', ' - ')


def strip_trailing_country_annotation(value, canonical_country):
    place = cleanup_value(value)
    while True:
        match = re.search(r'\s*\(([^()]*)\)\s*$', place)
        if not match:
            break
        inner = cleanup_country_variant(match.group(1))
        if not inner:
            break
        country_match = canonicalize_country_name(inner)
        if not country_match:
            break
        if (
            country_match['canonical_country'] != canonical_country
            or country_match['keep_in_settings']
        ):
            break
        place = place[:match.start()]
    return cleanup_setting_place(place)


def build_field_updates(existing_fields, field_specs, extracted_values, write_empty_to_custom_fields=False):
    current_values = {
        field_name: list(values or [])
        for field_name, values in (existing_fields or {}).items()
    }
    updates = {}

    for pref_name in ('character_field', 'settings_field', 'countries_field'):
        spec = field_specs.get(pref_name, {})
        field_name = spec.get('field_name', FIELD_NONE)
        if field_name == FIELD_NONE:
            continue

        incoming_values = extracted_values.get(pref_name, []) or []
        current_normalized = normalize_values_for_field(
            current_values.get(field_name, []),
            spec,
        )
        working_values = list(current_normalized)

        if incoming_values:
            working_values = merge_unique_values(working_values, incoming_values)
        elif not spec.get('is_tags') and write_empty_to_custom_fields:
            working_values = merge_unique_values(working_values, [_('Empty')])
        else:
            continue

        working_values = normalize_values_for_field(working_values, spec)

        payload = serialize_field_payload(working_values, spec)
        if payload is _SKIP_WRITE:
            continue

        original_payload = serialize_field_payload(current_normalized, spec)
        if payloads_equal(payload, original_payload):
            continue

        current_values[field_name] = list(working_values)
        updates[field_name] = payload

    return updates


def serialize_field_payload(values, spec):
    values = normalize_values_for_field(values, spec)
    if spec.get('is_tags'):
        return list(values) if values else _SKIP_WRITE
    if not values:
        return _SKIP_WRITE
    if spec.get('is_multiple'):
        return list(values)
    return ', '.join(values)


def payloads_equal(left, right):
    if left is _SKIP_WRITE and right is _SKIP_WRITE:
        return True
    if left is _SKIP_WRITE or right is _SKIP_WRITE:
        return False
    return left == right


def extract_goodreads_values(html, label):
    values = []
    labels = expand_label_aliases(label)
    debug_entries = []
    autodelete_values, autodelete_patterns = load_autodelete_values()

    for candidate in labels:
        json_values = extract_values_from_json(candidate, html)
        state_values = extract_values_from_embedded_state(candidate, html)
        detail_values = extract_values_from_detail_section(candidate, html)
        html_values = extract_values_from_html_block(candidate, html)

        values.extend(json_values)
        values.extend(state_values)
        values.extend(detail_values)
        values.extend(html_values)

        if debug_pref('debug_character_sources') and label.lower() == 'characters':
            debug_entries.extend(build_debug_entries('json', candidate, json_values))
            debug_entries.extend(build_debug_entries('state', candidate, state_values))
            debug_entries.extend(build_debug_entries('detail', candidate, detail_values))
            debug_entries.extend(build_debug_entries('html', candidate, html_values))

    deduped = []
    seen = set()
    for value in values:
        for normalized in normalize_extracted_value(value):
            if should_autodelete_value(normalized, autodelete_values, autodelete_patterns):
                continue
            if normalized and normalized not in seen:
                seen.add(normalized)
                deduped.append(normalized)

    if debug_pref('debug_character_sources') and label.lower() == 'characters':
        _LAST_EXTRACTION_DEBUG[label.lower()] = debug_entries

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
        values.extend(find_label_values_in_json(payload, label.lower(), label))
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
            values.extend(
                extract_keyed_values_from_embedded_state(
                    candidate_html,
                    key_name,
                    label,
                )
            )

        pattern = r'"name"\s*:\s*"{0}"'.format(re.escape(label))
        for match in re.finditer(pattern, candidate_html, flags=re.IGNORECASE):
            tail = candidate_html[match.end():match.end() + 12000]
            raw_values = extract_values_payload_from_tail(tail)
            if raw_values is not None:
                values.extend(extract_structured_values(raw_values, label))
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


def extract_keyed_values_from_embedded_state(html, key_name, label):
    values = []
    pattern = r'"{0}"\s*:'.format(re.escape(key_name))
    for match in re.finditer(pattern, html, flags=re.IGNORECASE):
        tail = html[match.end():]
        raw_values, consumed = extract_bracketed_json_payload(tail)
        if raw_values is None:
            continue
        values.extend(extract_structured_values(raw_values, label))
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


def find_label_values_in_json(node, label, original_label):
    matches = []
    if isinstance(node, dict):
        lower_keys = {str(key).lower(): key for key in node}
        name_key = lower_keys.get('name')
        values_key = lower_keys.get('values')
        if name_key is not None and values_key is not None:
            name = cleanup_value(node.get(name_key))
            if name and name.lower() == label:
                matches.extend(extract_structured_values(node.get(values_key), original_label))

        for value in node.values():
            matches.extend(find_label_values_in_json(value, label, original_label))
    elif isinstance(node, list):
        for value in node:
            matches.extend(find_label_values_in_json(value, label, original_label))
    return matches


def extract_structured_values(node, label):
    allowed_types = get_allowed_entity_types(label)
    values = extract_entity_values(node, allowed_types)
    return values


def get_allowed_entity_types(label):
    lower_label = label.lower()
    if lower_label in ('character', 'characters'):
        return ('character',)
    if lower_label in ('place', 'places', 'setting', 'settings'):
        return ('places', 'place', 'setting')
    return ()


def extract_entity_values(node, allowed_types):
    values = []
    if isinstance(node, list):
        for item in node:
            values.extend(extract_entity_values(item, allowed_types))
        return values

    if isinstance(node, str):
        parsed = try_parse_json_string(node)
        if parsed is not None:
            return extract_entity_values(parsed, allowed_types)
        return values

    if not isinstance(node, dict):
        return values

    entity_type = cleanup_value(node.get('__typename')).lower()
    if entity_type in allowed_types and entity_matches_allowed_link(node, allowed_types):
        formatted = format_json_value_object(node)
        if formatted:
            values.append(formatted)
        return values

    for child in node.values():
        if isinstance(child, (dict, list)):
            values.extend(extract_entity_values(child, allowed_types))
        elif isinstance(child, str):
            parsed = try_parse_json_string(child)
            if parsed is not None:
                values.extend(extract_entity_values(parsed, allowed_types))
    return values


def entity_matches_allowed_link(node, allowed_types):
    url = (
        cleanup_value(node.get('webUrl'))
        or cleanup_value(node.get('weburl'))
        or cleanup_value(node.get('url'))
        or cleanup_value(node.get('href'))
    )
    if not url:
        return True

    if 'character' in allowed_types:
        return href_matches_label(url, 'Characters')
    if 'places' in allowed_types or 'place' in allowed_types or 'setting' in allowed_types:
        return href_matches_label(url, 'Places')
    return True


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
        r'<a\b[^>]*href="(?P<href>[^"]*)"[^>]*>(?P<text>.*?)</a>',
        tail,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        href = anchor_match.group('href') or ''
        if not href_matches_label(href, label):
            continue
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
    for anchor_match in re.finditer(
        r'<a\b[^>]*href="(?P<href>[^"]*)"[^>]*>(?P<text>.*?)</a>',
        block,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        href = anchor_match.group('href') or ''
        if not href_matches_label(href, label):
            continue
        text = strip_tags(anchor_match.group('text'))
        if text and text.lower() != label.lower():
            values.append(text)

    if values:
        return values

    if get_allowed_entity_types(label):
        return []

    text = strip_tags(block)
    text = re.sub(r'\b{}\b'.format(re.escape(label)), '', text, flags=re.IGNORECASE)
    parts = [cleanup_value(part) for part in re.split(r'[\n|]+', text)]
    return [part for part in parts if part]


def format_settings(settings, keep_country_in_settings=True, keep_region_in_settings=True):
    if not settings:
        return [], []

    places = []
    countries = []
    seen_places = set()
    seen_countries = set()

    for value in settings:
        place_name, display_country, canonical_country = split_setting_value(value)
        if canonical_country:
            base_place = strip_trailing_country_annotation(place_name, canonical_country)
            region = display_country if keep_region_in_settings else ''
            if region:
                if base_place:
                    place = '{} - {}'.format(base_place, region)
                else:
                    place = region
            else:
                place = base_place

            if keep_country_in_settings and place:
                place = '{} ({})'.format(place, canonical_country)

            if place and place not in seen_places:
                seen_places.add(place)
                places.append(place)
            if canonical_country and canonical_country not in seen_countries:
                seen_countries.add(canonical_country)
                countries.append(canonical_country)
            continue

        place = cleanup_setting_place(value)
        whole_value_country = canonicalize_country_name(place)
        if whole_value_country:
            if whole_value_country['canonical_country'] not in seen_countries:
                seen_countries.add(whole_value_country['canonical_country'])
                countries.append(whole_value_country['canonical_country'])
            if keep_region_in_settings and whole_value_country['keep_in_settings'] and place and place not in seen_places:
                seen_places.add(place)
                places.append(place)
            continue
        if place and place not in seen_places:
            seen_places.add(place)
            places.append(place)

    return places, countries


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


def build_debug_entries(source_name, candidate_label, values):
    entries = []
    for value in values:
        entries.append({
            'source': source_name,
            'label': candidate_label,
            'raw': repr(value)[:400],
        })
    return entries


def href_matches_label(href, label):
    lower_href = (href or '').lower()
    lower_label = label.lower()

    if lower_label in ('character', 'characters'):
        return '/character/' in lower_href or '/characters/' in lower_href
    if lower_label in ('place', 'places', 'setting', 'settings'):
        return '/place/' in lower_href or '/places/' in lower_href
    return True


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
