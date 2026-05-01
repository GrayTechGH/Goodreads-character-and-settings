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
COUNTRY_NAME_LANGUAGE_AUTO = 'auto'
COUNTRY_NAME_LANGUAGE_ENGLISH_SHORT = 'en_short'
COUNTRY_NAME_LANGUAGE_ENGLISH_FORMAL = 'en_formal'
COUNTRY_NAME_MODE_ALIAS = 'alias'
COUNTRY_NAME_MODE_COUNTRY = 'country'
AUTODELETE_MODE_LITERAL = 'literal'
AUTODELETE_MODE_WILDCARD = 'wildcard'
AUTODELETE_MODE_REGEX = 'regex'
AUTODELETE_SCOPE_BOTH = 'both'
AUTODELETE_SCOPE_CHARACTERS = 'characters'
AUTODELETE_SCOPE_SETTINGS = 'settings'
USER_DATABASE_SCHEMA_VERSION = 3
COUNTRY_ISO_SCHEMA_VERSION = 2
_USER_JSON_REPAIR_FLAGS = {
    'countries': False,
    'regions': False,
    'autodelete': False,
}


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


def mark_user_json_for_repair(name):
    if name in _USER_JSON_REPAIR_FLAGS:
        _USER_JSON_REPAIR_FLAGS[name] = True


def consume_user_json_repair_flag(name):
    repaired = bool(_USER_JSON_REPAIR_FLAGS.get(name, False))
    if name in _USER_JSON_REPAIR_FLAGS:
        _USER_JSON_REPAIR_FLAGS[name] = False
    return repaired


def payload_schema_version(payload):
    if not isinstance(payload, dict):
        return 1
    try:
        return int(payload.get('schema_version') or 1)
    except Exception:
        return 1


def _normalize_country_record(country, aliases, iso='', infer_missing_iso=False):
    country = str(country or '').strip()
    iso = normalize_country_code(iso)
    if infer_missing_iso and not iso:
        iso = infer_country_iso(country, aliases)
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


def _normalize_region_record(country, region, iso='', infer_missing_iso=False):
    country = str(country or '').strip()
    iso = normalize_country_code(iso)
    if infer_missing_iso and not iso:
        iso = infer_country_iso(country)
    return {
        'country': country,
        'iso': iso,
        'region': str(region or '').strip(),
    }


def _normalize_autodelete_rule(item):
    if isinstance(item, dict):
        pattern = str(item.get('pattern') or item.get('value') or '').strip()
        mode = str(item.get('mode') or AUTODELETE_MODE_LITERAL).strip().lower()
        scope = str(item.get('scope') or AUTODELETE_SCOPE_BOTH).strip().lower()
        case_sensitive = bool(item.get('case_sensitive', False))
        enabled = bool(item.get('enabled', True))
    else:
        value = str(item or '').strip()
        pattern = value if '*' in value else '*{}*'.format(value)
        mode = AUTODELETE_MODE_WILDCARD
        scope = AUTODELETE_SCOPE_BOTH
        case_sensitive = False
        enabled = True

    if not pattern:
        return None
    if mode not in (AUTODELETE_MODE_LITERAL, AUTODELETE_MODE_WILDCARD, AUTODELETE_MODE_REGEX):
        mode = AUTODELETE_MODE_LITERAL
    if scope not in (AUTODELETE_SCOPE_BOTH, AUTODELETE_SCOPE_CHARACTERS, AUTODELETE_SCOPE_SETTINGS):
        scope = AUTODELETE_SCOPE_BOTH

    return {
        'pattern': pattern,
        'mode': mode,
        'scope': scope,
        'case_sensitive': case_sensitive,
        'enabled': enabled,
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


def _read_json(path, default, repair_key=None):
    if not os.path.exists(path):
        return default
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as err:
        if repair_key:
            mark_user_json_for_repair(repair_key)
        print(
            'Goodreads character and settings: failed to read {}: {}'.format(
                path,
                err,
            ),
            flush=True,
        )
        return default


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
    default_payload = {
        'schema_version': USER_DATABASE_SCHEMA_VERSION,
        'countries': build_default_user_data()['countries'],
    }
    payload = _read_json(countries_json_path(), default_payload, 'countries')
    if not isinstance(payload, dict):
        mark_user_json_for_repair('countries')
        payload = {'schema_version': 1, 'countries': payload if isinstance(payload, list) else []}
    infer_missing_iso = payload_schema_version(payload) < COUNTRY_ISO_SCHEMA_VERSION
    countries = []
    for item in payload.get('countries', []) or []:
        if isinstance(item, dict):
            country = str(item.get('country') or '').strip()
            iso = item.get('iso', '')
            aliases = list(item.get('aliases', []) or [])
        else:
            mark_user_json_for_repair('countries')
            continue
        if not country:
            mark_user_json_for_repair('countries')
            continue
        country_record = _normalize_country_record(
            country,
            aliases,
            iso,
            infer_missing_iso=infer_missing_iso,
        )
        if country_record != item:
            mark_user_json_for_repair('countries')
        countries.append(country_record)
    countries.sort(key=lambda entry: entry['country'].lower())
    return countries


def load_user_region_data():
    ensure_user_json_files()
    default_payload = {
        'schema_version': USER_DATABASE_SCHEMA_VERSION,
        'regions': build_default_user_data()['regions'],
    }
    payload = _read_json(regions_json_path(), default_payload, 'regions')
    if not isinstance(payload, dict):
        mark_user_json_for_repair('regions')
        payload = {'schema_version': 1, 'regions': payload if isinstance(payload, list) else []}
    infer_missing_iso = payload_schema_version(payload) < COUNTRY_ISO_SCHEMA_VERSION
    regions = []
    for item in payload.get('regions', []) or []:
        if not isinstance(item, dict):
            mark_user_json_for_repair('regions')
            continue
        region = _normalize_region_record(
            item.get('country'),
            item.get('region'),
            item.get('iso', ''),
            infer_missing_iso=infer_missing_iso,
        )
        if region['country'] and region['region']:
            if region != item:
                mark_user_json_for_repair('regions')
            regions.append(region)
        else:
            mark_user_json_for_repair('regions')
    regions.sort(key=lambda entry: (entry['iso'], entry['country'].lower(), entry['region'].lower()))
    return regions


def load_user_autodelete_values():
    ensure_user_json_files()
    payload = _read_json(
        autodelete_json_path(),
        {'schema_version': USER_DATABASE_SCHEMA_VERSION, 'rules': []},
        'autodelete',
    )
    if not isinstance(payload, dict):
        mark_user_json_for_repair('autodelete')
        payload = {'schema_version': 1, 'values': payload if isinstance(payload, list) else []}
    values = payload.get('rules')
    if values is None:
        values = payload.get('values', [])
        if values:
            mark_user_json_for_repair('autodelete')
    rules = []
    seen = set()
    for item in values or []:
        rule = _normalize_autodelete_rule(item)
        if not rule:
            mark_user_json_for_repair('autodelete')
            continue
        key = (
            rule['pattern'].casefold(),
            rule['mode'],
            rule['scope'],
            rule['case_sensitive'],
        )
        if key in seen:
            mark_user_json_for_repair('autodelete')
            continue
        seen.add(key)
        if not isinstance(item, dict) or rule != item:
            mark_user_json_for_repair('autodelete')
        rules.append(rule)
    rules.sort(key=lambda item: (item['pattern'].casefold(), item['mode'], item['scope']))
    return rules


def save_user_country_data(countries, infer_missing_iso=False):
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
            infer_missing_iso=infer_missing_iso,
        ))
    normalized.sort(key=lambda entry: entry['country'].lower())
    _write_json(countries_json_path(), {
        'schema_version': USER_DATABASE_SCHEMA_VERSION,
        'countries': normalized,
    })


def save_user_region_data(regions, infer_missing_iso=False):
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
            infer_missing_iso=infer_missing_iso,
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
        rule = _normalize_autodelete_rule(item)
        if not rule:
            continue
        key = (
            rule['pattern'].casefold(),
            rule['mode'],
            rule['scope'],
            rule['case_sensitive'],
        )
        if key in seen:
            continue
        seen.add(key)
        normalized.append(rule)
    normalized.sort(key=lambda item: (item['pattern'].casefold(), item['mode'], item['scope']))
    _write_json(autodelete_json_path(), {
        'schema_version': USER_DATABASE_SCHEMA_VERSION,
        'rules': normalized,
    })
