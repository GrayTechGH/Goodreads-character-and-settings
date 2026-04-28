#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


from __future__ import print_function

import json
import os
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESOURCES = os.path.join(ROOT, 'resources')


def resource_path(filename):
    return os.path.join(RESOURCES, filename)


def read_json(filename):
    with open(resource_path(filename), 'r', encoding='utf-8') as f:
        return json.load(f)


def require(condition, message, errors):
    if not condition:
        errors.append(message)


def validate_country_names(errors):
    payload = read_json('default_country_names.json')

    languages = payload.get('languages')
    country_names = payload.get('country_names')
    require(isinstance(languages, list), 'default_country_names.json: languages must be a list', errors)
    require(isinstance(country_names, dict), 'default_country_names.json: country_names must be an object', errors)
    if not isinstance(languages, list) or not isinstance(country_names, dict):
        return set(), set()

    language_codes = set(languages)
    require(len(language_codes) == len(languages),
            'default_country_names.json: languages contains duplicate codes', errors)
    country_language_codes = set(country_names)
    require(language_codes == country_language_codes,
            'default_country_names.json: languages and country_names language codes differ', errors)
    require('en' in country_names, 'default_country_names.json: missing English country names', errors)

    english_country_codes = set(country_names.get('en', {}).get('countries', {}))
    require(bool(english_country_codes), 'default_country_names.json: English countries list is empty', errors)

    for language_code, language_payload in sorted(country_names.items()):
        countries = language_payload.get('countries') if isinstance(language_payload, dict) else None
        require(isinstance(countries, dict),
                'default_country_names.json: {} countries must be an object'.format(language_code), errors)
        if not isinstance(countries, dict):
            continue

        country_codes = set(countries)
        require(country_codes == english_country_codes,
                'default_country_names.json: {} country code coverage differs from English'.format(language_code), errors)

        for country_code, country_payload in sorted(countries.items()):
            path = 'default_country_names.json: {}.{}'.format(language_code, country_code)
            require(isinstance(country_code, str) and len(country_code) == 2 and country_code.upper() == country_code,
                    '{} country code must be two uppercase letters'.format(path), errors)

            if language_code != 'en':
                require(isinstance(country_payload, str) and bool(country_payload.strip()),
                        '{} must be a non-empty localized country name string'.format(path), errors)
                continue

            require(isinstance(country_payload, dict), '{} must be an object'.format(path), errors)
            if not isinstance(country_payload, dict):
                continue
            short_name = country_payload.get('short')
            formal_names = country_payload.get('formal')
            require(isinstance(short_name, str) and bool(short_name.strip()),
                    '{} short must be a non-empty string'.format(path), errors)
            require(isinstance(formal_names, list), '{} formal must be a list'.format(path), errors)
            if isinstance(formal_names, list):
                for formal_name in formal_names:
                    require(isinstance(formal_name, str) and bool(formal_name.strip()),
                            '{} formal values must be non-empty strings'.format(path), errors)

    return language_codes, english_country_codes


def validate_country_regions(country_codes, errors):
    payload = read_json('default_country_regions.json')
    regions_by_country = payload.get('regions_by_country') if isinstance(payload, dict) else None
    require(isinstance(regions_by_country, dict),
            'default_country_regions.json: regions_by_country must be an object', errors)
    if not isinstance(regions_by_country, dict):
        return

    region_country_codes = set(regions_by_country)
    require(region_country_codes == country_codes,
            'default_country_regions.json: country code coverage differs from default_country_names.json English countries',
            errors)

    for country_code, regions in sorted(regions_by_country.items()):
        path = 'default_country_regions.json: {}'.format(country_code)
        require(isinstance(regions, list), '{} regions must be a list'.format(path), errors)
        if not isinstance(regions, list):
            continue
        seen = set()
        for region in regions:
            require(isinstance(region, str) and bool(region.strip()),
                    '{} region values must be non-empty strings'.format(path), errors)
            if isinstance(region, str):
                require(region not in seen, '{} duplicate region: {}'.format(path, region), errors)
                seen.add(region)


def main():
    errors = []
    language_codes, country_codes = validate_country_names(errors)
    validate_country_regions(country_codes, errors)

    if errors:
        print('Resource validation failed:')
        for error in errors:
            print(' - {}'.format(error))
        return 1

    print('Resource validation passed.')
    print('Languages: {}'.format(len(language_codes)))
    print('Countries: {}'.format(len(country_codes)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
