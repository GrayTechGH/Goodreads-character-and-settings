#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2026, GrayTechGH'
__docformat__ = 'restructuredtext en'

import json
import os

from calibre_plugins.Goodreads_character_and_settings.config import prefs
from calibre_plugins.Goodreads_character_and_settings.settings_data import (
    AUTODELETE_FILE,
    COUNTRIES_FILE,
    REGIONS_FILE,
    USER_DATABASE_SCHEMA_VERSION,
    autodelete_json_path,
    countries_json_path,
    ensure_user_json_files,
    plugin_data_dir,
    regions_json_path,
    save_user_autodelete_values,
    save_user_country_data,
    save_user_region_data,
)


DATABASE_VERSION_PREF = 'database_version'
LEGACY_USER_DATABASE_SCHEMA_VERSION = 1

prefs.defaults[DATABASE_VERSION_PREF] = (0, 0, 0)


def current_plugin_version():
    from calibre_plugins.Goodreads_character_and_settings.__init__ import GoodreadsCharacterSettingsPlugin

    return normalize_version(GoodreadsCharacterSettingsPlugin.version)


def normalize_version(version):
    if version is None:
        return (0, 0, 0)
    if isinstance(version, str):
        parts = version.split('.')
    else:
        parts = list(version)

    normalized = []
    for part in parts:
        try:
            normalized.append(int(part))
        except Exception:
            normalized.append(0)

    while len(normalized) < 3:
        normalized.append(0)
    return tuple(normalized[:3])


def get_database_version():
    return normalize_version(prefs[DATABASE_VERSION_PREF])


def set_database_version(version):
    prefs[DATABASE_VERSION_PREF] = list(normalize_version(version))


def read_json_file(path, default):
    if not os.path.exists(path):
        return default
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def payload_schema_version(payload):
    if not isinstance(payload, dict):
        return LEGACY_USER_DATABASE_SCHEMA_VERSION
    try:
        return int(payload.get('schema_version') or LEGACY_USER_DATABASE_SCHEMA_VERSION)
    except Exception:
        return LEGACY_USER_DATABASE_SCHEMA_VERSION


def user_database_versions():
    versions = {}
    paths = (
        (COUNTRIES_FILE, countries_json_path()),
        (REGIONS_FILE, regions_json_path()),
        (AUTODELETE_FILE, autodelete_json_path()),
    )
    for name, path in paths:
        if os.path.exists(path):
            versions[name] = payload_schema_version(read_json_file(path, {}))
        else:
            versions[name] = 0
    return versions


def needs_user_database_schema_update():
    return any(
        version < USER_DATABASE_SCHEMA_VERSION
        for version in user_database_versions().values()
    )


def split_values(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = str(value).split(',')

    cleaned = []
    for item in values:
        text = str(item or '').strip()
        if text:
            cleaned.append(text)
    return cleaned


def normalize_legacy_country_rows(payload):
    if isinstance(payload, dict) and isinstance(payload.get('countries'), list):
        source_rows = payload.get('countries', [])
    elif isinstance(payload, list):
        source_rows = payload
    elif isinstance(payload, dict):
        source_rows = [
            {'country': country, 'variants': variants}
            for country, variants in payload.items()
        ]
    else:
        source_rows = []

    rows = []
    for item in source_rows:
        if not isinstance(item, dict):
            continue
        country = str(item.get('country') or item.get('name') or '').strip()
        iso = str(
            item.get('iso') or item.get('iso_country_code') or item.get('code') or ''
        ).strip()
        aliases = item.get('aliases')

        variants = item.get('variants')
        if not iso and isinstance(variants, dict):
            iso = str(
                variants.get('iso') or variants.get('iso_country_code') or variants.get('code') or ''
            ).strip()
        if aliases is None and isinstance(variants, dict):
            aliases = variants.get('replace', variants.get('replace_in_settings', []))
        elif aliases is None and variants is not None:
            aliases = variants
        elif aliases is None:
            aliases = item.get('replace', item.get('replace_in_settings', []))

        if country:
            rows.append({
                'country': country,
                'iso': iso,
                'aliases': split_values(aliases),
            })
    return rows


def append_region_rows(rows, country, regions, iso=''):
    country = str(country or '').strip()
    if not country:
        return
    for region in split_values(regions):
        rows.append({
            'country': country,
            'iso': iso,
            'region': region,
        })


def normalize_legacy_region_rows(payload):
    rows = []
    if isinstance(payload, dict) and isinstance(payload.get('regions'), list):
        source_rows = payload.get('regions', [])
        for item in source_rows:
            if not isinstance(item, dict):
                continue
            if 'region' in item:
                append_region_rows(
                    rows,
                    item.get('country'),
                    [item.get('region')],
                    item.get('iso', ''),
                )
            else:
                append_region_rows(
                    rows,
                    item.get('country') or item.get('name'),
                    item.get('regions', item.get('keep_in_settings', [])),
                    item.get('iso', ''),
                )
        return rows

    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                if 'region' in item:
                    append_region_rows(
                        rows,
                        item.get('country'),
                        [item.get('region')],
                        item.get('iso', ''),
                    )
                else:
                    append_region_rows(
                        rows,
                        item.get('country') or item.get('name'),
                        item.get('regions', item.get('keep_in_settings', [])),
                        item.get('iso', ''),
                    )
        return rows

    if isinstance(payload, dict):
        for country, variants in payload.items():
            iso = ''
            if isinstance(variants, dict):
                iso = variants.get('iso', '')
                regions = variants.get('regions', variants.get('keep_in_settings', []))
            else:
                regions = []
            append_region_rows(rows, country, regions, iso)
    return rows


def migrate_user_country_region_files():
    if not os.path.exists(plugin_data_dir()):
        os.makedirs(plugin_data_dir())

    if os.path.exists(countries_json_path()):
        save_user_country_data(
            normalize_legacy_country_rows(
                read_json_file(countries_json_path(), {'countries': []})
            )
        )

    if os.path.exists(regions_json_path()):
        save_user_region_data(
            normalize_legacy_region_rows(
                read_json_file(regions_json_path(), {'regions': []})
            )
        )

    if os.path.exists(autodelete_json_path()):
        payload = read_json_file(autodelete_json_path(), {'values': []})
        values = payload.get('values', []) if isinstance(payload, dict) else payload
        save_user_autodelete_values(values)


def update_database_from_version(from_version=None, to_version=None):
    previous_version = normalize_version(from_version) if from_version is not None else get_database_version()
    target_version = normalize_version(to_version) if to_version is not None else current_plugin_version()
    applied_updates = []

    if previous_version < (1, 0, 0) <= target_version:
        ensure_user_json_files(force_reset=False)
        applied_updates.append('ensure_user_json_files')

    if (
        previous_version < (1, 0, 1) <= target_version
        or needs_user_database_schema_update()
    ):
        migrate_user_country_region_files()
        ensure_user_json_files(force_reset=False)
        applied_updates.append('migrate_user_country_region_files')

    set_database_version(target_version)
    return {
        'from_version': previous_version,
        'to_version': target_version,
        'applied_updates': applied_updates,
    }
