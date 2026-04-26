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


def plugin_data_dir():
    return os.path.join(config_dir, 'plugins', PLUGIN_DATA_FOLDER)


def countries_json_path():
    return os.path.join(plugin_data_dir(), COUNTRIES_FILE)


def regions_json_path():
    return os.path.join(plugin_data_dir(), REGIONS_FILE)


def autodelete_json_path():
    return os.path.join(plugin_data_dir(), AUTODELETE_FILE)


def _read_bundled_country_variants():
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
            '{}/resources/country_variants.json'.format(internal_prefix).strip('/'),
            'resources/country_variants.json',
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

    resource_path = os.path.join(os.path.dirname(__file__), 'resources', 'country_variants.json')
    with open(resource_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _normalize_country_record(country, aliases):
    country = str(country or '').strip()
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
        'aliases': cleaned_aliases,
    }


def _normalize_region_record(country, region):
    return {
        'country': str(country or '').strip(),
        'region': str(region or '').strip(),
    }


def build_default_user_data():
    bundled = _read_bundled_country_variants()
    countries = []
    regions = []

    for canonical_country, variants in bundled.items():
        replace_in_settings = []
        keep_in_settings = []

        if isinstance(variants, dict):
            replace_in_settings = list(variants.get('replace_in_settings', []) or [])
            keep_in_settings = list(variants.get('keep_in_settings', []) or [])
        else:
            replace_in_settings = list(variants or [])

        countries.append(
            _normalize_country_record(canonical_country, replace_in_settings)
        )

        for region in keep_in_settings:
            region_record = _normalize_region_record(canonical_country, region)
            if region_record['country'] and region_record['region']:
                regions.append(region_record)

    countries.sort(key=lambda item: item['country'].lower())
    regions.sort(key=lambda item: (item['country'].lower(), item['region'].lower()))
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
        _write_json(countries_json_path(), {'countries': defaults['countries']})
    if force_reset or not os.path.exists(regions_json_path()):
        _write_json(regions_json_path(), {'regions': defaults['regions']})
    if force_reset or not os.path.exists(autodelete_json_path()):
        _write_json(autodelete_json_path(), {'values': defaults['autodelete']})


def load_user_country_data():
    ensure_user_json_files()
    payload = _read_json(countries_json_path(), {'countries': []})
    countries = []
    for item in payload.get('countries', []) or []:
        if isinstance(item, dict):
            country = str(item.get('country') or '').strip()
            aliases = list(item.get('aliases', []) or [])
        else:
            continue
        if not country:
            continue
        countries.append(_normalize_country_record(country, aliases))
    countries.sort(key=lambda entry: entry['country'].lower())
    return countries


def load_user_region_data():
    ensure_user_json_files()
    payload = _read_json(regions_json_path(), {'regions': []})
    regions = []
    for item in payload.get('regions', []) or []:
        if not isinstance(item, dict):
            continue
        region = _normalize_region_record(item.get('country'), item.get('region'))
        if region['country'] and region['region']:
            regions.append(region)
    regions.sort(key=lambda entry: (entry['country'].lower(), entry['region'].lower()))
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
        normalized.append(_normalize_country_record(country, item.get('aliases', [])))
    normalized.sort(key=lambda entry: entry['country'].lower())
    _write_json(countries_json_path(), {'countries': normalized})


def save_user_region_data(regions):
    ensure_user_json_files()
    normalized = []
    seen = set()
    for item in regions or []:
        if not isinstance(item, dict):
            continue
        region = _normalize_region_record(item.get('country'), item.get('region'))
        if not region['country'] or not region['region']:
            continue
        key = (region['country'].lower(), region['region'].lower())
        if key in seen:
            continue
        seen.add(key)
        normalized.append(region)
    normalized.sort(key=lambda entry: (entry['country'].lower(), entry['region'].lower()))
    _write_json(regions_json_path(), {'regions': normalized})


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
    _write_json(autodelete_json_path(), {'values': normalized})
