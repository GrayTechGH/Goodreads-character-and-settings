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
from fnmatch import fnmatchcase
from html import unescape

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

from calibre_plugins.Goodreads_character_and_settings.settings_data import (
    ensure_user_json_files,
    load_user_autodelete_values,
    load_user_country_data,
    load_user_region_data,
    plugin_data_dir,
)


FIELD_NONE = 'none'
_SKIP_WRITE = object()
_LAST_EXTRACTION_DEBUG = {}
_COUNTRY_VARIANT_LOOKUP = None
_COUNTRY_VARIANT_PATTERNS = None
_COUNTRY_VARIANT_SOURCE = ''
_AUTODELETE_VALUES = None
_AUTODELETE_PATTERNS = None


def reset_runtime_caches():
    global _COUNTRY_VARIANT_LOOKUP, _COUNTRY_VARIANT_PATTERNS, _COUNTRY_VARIANT_SOURCE, _AUTODELETE_VALUES, _AUTODELETE_PATTERNS
    _COUNTRY_VARIANT_LOOKUP = None
    _COUNTRY_VARIANT_PATTERNS = None
    _COUNTRY_VARIANT_SOURCE = ''
    _AUTODELETE_VALUES = None
    _AUTODELETE_PATTERNS = None


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


def remove_empty_marker(values):
    empty_marker = cleanup_value(_('Empty')).casefold()
    return [
        value for value in values or []
        if cleanup_value(value).casefold() != empty_marker
    ]


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
            if write_empty_to_custom_fields:
                working_values = remove_empty_marker(working_values)
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
        # Goodreads stores character and place entities in the React hydration payload.
        next_data_values = extract_values_from_next_data(candidate, html)

        values.extend(next_data_values)

        if debug_pref('debug_character_sources') and label.lower() == 'characters':
            debug_entries.extend(build_debug_entries('next_data', candidate, next_data_values))

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


def extract_values_from_next_data(label, html):
    soup = parse_goodreads_html(html)
    if soup is None:
        return []

    script_node = soup.find('script', attrs={'id': '__NEXT_DATA__'})
    if script_node is None:
        return []

    raw_payload = script_node.string or script_node.get_text() or ''
    try:
        payload = json.loads(raw_payload)
    except Exception:
        return []

    return extract_entity_values(payload, get_allowed_entity_types(label))


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
    cleaned = cleanup_value(value)
    return [cleaned] if cleaned else []


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


def parse_goodreads_html(html):
    if BeautifulSoup is None:
        return None
    return BeautifulSoup(html or '', 'html.parser')


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


def strip_tags(text):
    return re.sub(r'<[^>]+>', ' ', text or '')
