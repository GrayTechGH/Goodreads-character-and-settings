#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2026, GrayTechGH'
__docformat__ = 'restructuredtext en'

import json
import os
import zipfile

from calibre.constants import config_dir


PLUGIN_DATA_FOLDER = 'Goodreads_character_and_settings'
COUNTRIES_FILE = 'countries.json'
REGIONS_FILE = 'regions.json'
AUTODELETE_FILE = 'autodelete.json'
COUNTRY_NAMES_FILE = 'default_country_names.json'
COUNTRY_REGIONS_FILE = 'default_country_regions.json'
PLUGIN_UI_TRANSLATIONS_FILE = 'plugin_ui_translations.json'
COUNTRY_NAME_LANGUAGE_AUTO = 'auto'
COUNTRY_NAME_LANGUAGE_ENGLISH_SHORT = 'en_short'
COUNTRY_NAME_LANGUAGE_ENGLISH_FORMAL = 'en_formal'
COUNTRY_NAME_MODE_ALIAS = 'alias'
COUNTRY_NAME_MODE_COUNTRY = 'country'
USER_DATABASE_SCHEMA_VERSION = 2


def plugin_data_dir():
    return os.path.join(config_dir, 'plugins', PLUGIN_DATA_FOLDER)


def countries_json_path():
    return os.path.join(plugin_data_dir(), COUNTRIES_FILE)


def regions_json_path():
    return os.path.join(plugin_data_dir(), REGIONS_FILE)


def autodelete_json_path():
    return os.path.join(plugin_data_dir(), AUTODELETE_FILE)


def bundled_resource_path(filename):
    return os.path.join(os.path.dirname(__file__), 'resources', filename)


def _read_bundled_json_resource(filename):
    module_path = os.path.abspath(__file__)
    zip_marker = '.zip' + os.sep
    lower_module_path = module_path.lower()
    marker_index = lower_module_path.find(zip_marker)
    if marker_index >= 0:
        archive_path = module_path[:marker_index + 4]
        internal_prefix = module_path[marker_index + len(zip_marker):].replace('\\', '/')
        if '/' in internal_prefix:
            internal_prefix = internal_prefix.rsplit('/', 1)[0]
        else:
            internal_prefix = ''
        candidates = [
            '{}/resources/{}'.format(internal_prefix, filename).strip('/'),
            'resources/{}'.format(filename),
        ]
        seen = set()
        for candidate in candidates:
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            try:
                with zipfile.ZipFile(archive_path, 'r') as zf:
                    return json.loads(zf.read(candidate).decode('utf-8'))
            except Exception:
                pass

    resource_path = bundled_resource_path(filename)
    with open(resource_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _read_bundled_country_regions():
    return _read_bundled_json_resource(COUNTRY_REGIONS_FILE)


def _read_bundled_country_names():
    return _read_bundled_json_resource(COUNTRY_NAMES_FILE)


def read_bundled_plugin_ui_translations():
    return _read_bundled_json_resource(PLUGIN_UI_TRANSLATIONS_FILE)


def normalize_country_code(value):
    return str(value or '').strip().upper()


def default_country_iso_lookup():
    cached = getattr(default_country_iso_lookup, 'cached', None)
    if cached is not None:
        return cached

    lookup = {}
    try:
        country_names = _read_bundled_country_names()
        for language in country_names.get('country_names', {}).values():
            for iso, localized_entry in (language.get('countries', {}) or {}).items():
                short_name, formal_names = country_name_values(localized_entry)
                for value in [short_name] + formal_names:
                    text = str(value or '').strip()
                    if text:
                        lookup.setdefault(text.casefold(), normalize_country_code(iso))
    except Exception:
        pass

    default_country_iso_lookup.cached = lookup
    return lookup


def infer_country_iso(country, aliases=None):
    lookup = default_country_iso_lookup()
    for value in [country] + list(aliases or []):
        text = str(value or '').strip()
        if not text:
            continue
        iso = lookup.get(text.casefold())
        if iso:
            return iso
    return ''


def _normalize_country_record(country, aliases, iso=''):
    country = str(country or '').strip()
    iso = normalize_country_code(iso) or infer_country_iso(country, aliases)
    cleaned_aliases = []
    seen = set()
    if country:
        cleaned_aliases.append(country)
        seen.add(country.lower())
    for alias in aliases or []:
        value = str(alias or '').strip()
        if not value:
            continue
        lowered = value.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        cleaned_aliases.append(value)
    return {
        'country': country,
        'iso': iso,
        'aliases': cleaned_aliases,
    }


def _normalize_region_record(country, region, iso=''):
    country = str(country or '').strip()
    return {
        'country': country,
        'iso': normalize_country_code(iso) or infer_country_iso(country),
        'region': str(region or '').strip(),
    }


def active_language_code():
    try:
        from calibre.utils.localization import get_lang
        return str(get_lang() or 'en').replace('-', '_')
    except Exception:
        return 'en'


def resolve_country_name_language(language, country_names):
    language = str(language or COUNTRY_NAME_LANGUAGE_AUTO).strip()
    if language in (COUNTRY_NAME_LANGUAGE_ENGLISH_SHORT, COUNTRY_NAME_LANGUAGE_ENGLISH_FORMAL):
        return 'en'
    if language == COUNTRY_NAME_LANGUAGE_AUTO:
        language = active_language_code()
    language = language.replace('-', '_')
    available = country_names.get('country_names', {})
    if language in available:
        return language
    base_language = language.split('_', 1)[0]
    if base_language in available:
        return base_language
    return 'en'


def localized_country_names_for_language(language):
    country_names = _read_bundled_country_names()
    resolved_language = resolve_country_name_language(language, country_names)
    return country_names.get('country_names', {}).get(resolved_language, {}).get('countries', {})


def country_name_language_uses_formal_english(language):
    return str(language or '').strip() == COUNTRY_NAME_LANGUAGE_ENGLISH_FORMAL


def country_name_language_options():
    country_names = _read_bundled_country_names()
    return list(country_names.get('languages', []) or [])


def country_name_language_display_name(language):
    language = str(language or '').replace('-', '_')
    if language == COUNTRY_NAME_LANGUAGE_ENGLISH_SHORT:
        return 'English short names'
    if language == COUNTRY_NAME_LANGUAGE_ENGLISH_FORMAL:
        return 'English formal names'
    try:
        from calibre.utils.localization import countrycode_to_name, get_language
        language_code, _separator, country_code = language.partition('_')
        language_name = get_language(language_code)
        if country_code:
            country_name = countrycode_to_name(country_code)
            return '{} ({})'.format(language_name, country_name)
        return language_name
    except Exception:
        return language


def country_name_values(localized_entry):
    if isinstance(localized_entry, dict):
        short_name = str(localized_entry.get('short') or '').strip()
        formal_names = [
            str(item or '').strip()
            for item in localized_entry.get('formal', []) or []
            if str(item or '').strip()
        ]
        return short_name, formal_names
    return str(localized_entry or '').strip(), []


def build_default_user_data(country_name_language=COUNTRY_NAME_LANGUAGE_AUTO, country_name_mode=COUNTRY_NAME_MODE_ALIAS):
    country_names = _read_bundled_country_names()
    localized_names = localized_country_names_for_language(country_name_language)
    english_names = country_names.get('country_names', {}).get('en', {}).get('countries', {})
    regions_by_country = _read_bundled_country_regions().get('regions_by_country', {})
    use_formal_english = country_name_language_uses_formal_english(country_name_language)
    country_name_mode = str(country_name_mode or COUNTRY_NAME_MODE_ALIAS)
    countries = []
    regions = []

    for iso_code in sorted(english_names):
        iso_code = normalize_country_code(iso_code)
        canonical_country, english_formal_names = country_name_values(english_names.get(iso_code))
        if not canonical_country:
            continue
        localized_name, formal_names = country_name_values(localized_names.get(iso_code))
        if not localized_name:
            localized_name = canonical_country
        if use_formal_english and formal_names:
            localized_name = formal_names[0]
            formal_names = formal_names[1:]
        country_name = canonical_country
        replace_in_settings = [canonical_country] + english_formal_names
        keep_in_settings = list(regions_by_country.get(iso_code, []) or [])

        if country_name_mode == COUNTRY_NAME_MODE_COUNTRY and localized_name:
            country_name = localized_name
            replace_in_settings = list(replace_in_settings) + [canonical_country]
            if localized_name != canonical_country:
                replace_in_settings = list(replace_in_settings) + [localized_name]
        elif localized_name:
            replace_in_settings = list(replace_in_settings) + [localized_name]
        replace_in_settings = list(replace_in_settings) + formal_names

        countries.append(
            _normalize_country_record(country_name, replace_in_settings, iso_code)
        )

        for region in keep_in_settings:
            region_record = _normalize_region_record(country_name, region, iso_code)
            if region_record['country'] and region_record['region']:
                regions.append(region_record)

    countries.sort(key=lambda item: item['country'].lower())
    regions.sort(key=lambda item: (item['iso'], item['country'].lower(), item['region'].lower()))
    return {
        'countries': countries,
        'regions': regions,
        'autodelete': [],
    }


def _write_json(path, payload):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=False)


def _read_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def ensure_user_json_files(force_reset=False):
    data_dir = plugin_data_dir()
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    defaults = build_default_user_data()
    if force_reset or not os.path.exists(countries_json_path()):
        _write_json(countries_json_path(), {
            'schema_version': USER_DATABASE_SCHEMA_VERSION,
            'countries': defaults['countries'],
        })
    if force_reset or not os.path.exists(regions_json_path()):
        _write_json(regions_json_path(), {
            'schema_version': USER_DATABASE_SCHEMA_VERSION,
            'regions': defaults['regions'],
        })
    if force_reset or not os.path.exists(autodelete_json_path()):
        _write_json(autodelete_json_path(), {
            'schema_version': USER_DATABASE_SCHEMA_VERSION,
            'values': defaults['autodelete'],
        })


def load_user_country_data():
    ensure_user_json_files()
    payload = _read_json(countries_json_path(), {'countries': []})
    countries = []
    for item in payload.get('countries', []) or []:
        if isinstance(item, dict):
            country = str(item.get('country') or '').strip()
            iso = item.get('iso', '')
            aliases = list(item.get('aliases', []) or [])
        else:
            continue
        if not country:
            continue
        countries.append(_normalize_country_record(country, aliases, iso))
    countries.sort(key=lambda entry: entry['country'].lower())
    return countries


def load_user_region_data():
    ensure_user_json_files()
    payload = _read_json(regions_json_path(), {'regions': []})
    regions = []
    for item in payload.get('regions', []) or []:
        if not isinstance(item, dict):
            continue
        region = _normalize_region_record(
            item.get('country'),
            item.get('region'),
            item.get('iso', ''),
        )
        if region['country'] and region['region']:
            regions.append(region)
    regions.sort(key=lambda entry: (entry['iso'], entry['country'].lower(), entry['region'].lower()))
    return regions


def load_user_autodelete_values():
    ensure_user_json_files()
    payload = _read_json(autodelete_json_path(), {'values': []})
    values = []
    seen = set()
    for item in payload.get('values', []) or []:
        value = str(item or '').strip()
        if not value:
            continue
        lowered = value.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        values.append(value)
    values.sort(key=lambda item: item.lower())
    return values


def save_user_country_data(countries):
    ensure_user_json_files()
    normalized = []
    for item in countries or []:
        if not isinstance(item, dict):
            continue
        country = str(item.get('country') or '').strip()
        if not country:
            continue
        normalized.append(_normalize_country_record(
            country,
            item.get('aliases', []),
            item.get('iso', ''),
        ))
    normalized.sort(key=lambda entry: entry['country'].lower())
    _write_json(countries_json_path(), {
        'schema_version': USER_DATABASE_SCHEMA_VERSION,
        'countries': normalized,
    })


def save_user_region_data(regions):
    ensure_user_json_files()
    normalized = []
    seen = set()
    for item in regions or []:
        if not isinstance(item, dict):
            continue
        region = _normalize_region_record(
            item.get('country'),
            item.get('region'),
            item.get('iso', ''),
        )
        if not region['country'] or not region['region']:
            continue
        country_key = region['iso'] or region['country'].casefold()
        key = (country_key, region['region'].lower())
        if key in seen:
            continue
        seen.add(key)
        normalized.append(region)
    normalized.sort(key=lambda entry: (entry['iso'], entry['country'].lower(), entry['region'].lower()))
    _write_json(regions_json_path(), {
        'schema_version': USER_DATABASE_SCHEMA_VERSION,
        'regions': normalized,
    })


def save_user_autodelete_values(values):
    ensure_user_json_files()
    normalized = []
    seen = set()
    for item in values or []:
        value = str(item or '').strip()
        if not value:
            continue
        lowered = value.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(value)
    normalized.sort(key=lambda item: item.lower())
    _write_json(autodelete_json_path(), {
        'schema_version': USER_DATABASE_SCHEMA_VERSION,
        'values': normalized,
    })
