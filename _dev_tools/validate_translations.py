#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


from __future__ import print_function

import os
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANSLATION_SOURCES = os.path.join(ROOT, '_dev_tools', 'translations')
RUNTIME_TRANSLATIONS = os.path.join(ROOT, 'translations')
TEMPLATE = 'goodreads_cs.pot'


def require(condition, message, errors):
    if not condition:
        errors.append(message)


def unescape_po_string(value):
    return bytes(value, 'utf-8').decode('unicode_escape')


def parse_po(path):
    entries = {}
    header_seen = False
    current_id = None
    current_str = None
    mode = None

    with open(path, 'r', encoding='utf-8') as f:
        for line_number, raw_line in enumerate(f, 1):
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue

            if line.startswith('msgid '):
                raw_value = line[6:].strip()
                current_id = unescape_po_string(raw_value[1:-1])
                current_str = None
                mode = 'id'
                continue

            if line.startswith('msgstr '):
                raw_value = line[7:].strip()
                current_str = unescape_po_string(raw_value[1:-1])
                mode = 'str'
                if current_id == '':
                    header_seen = True
                elif current_id is not None:
                    entries[current_id] = current_str
                continue

            if line.startswith('"') and line.endswith('"'):
                value = unescape_po_string(line[1:-1])
                if mode == 'id' and current_id is not None:
                    current_id += value
                elif mode == 'str' and current_id is not None:
                    current_str = (current_str or '') + value
                    if current_id != '':
                        entries[current_id] = current_str
                continue

            raise ValueError('{}:{} unsupported .po syntax: {}'.format(path, line_number, raw_line.rstrip()))

    return entries, header_seen


def validate_po_sources(errors):
    template_path = os.path.join(TRANSLATION_SOURCES, TEMPLATE)
    require(os.path.isdir(TRANSLATION_SOURCES),
            'missing translation source directory: {}'.format(TRANSLATION_SOURCES), errors)
    require(os.path.exists(template_path),
            'missing translation template: {}'.format(template_path), errors)
    if not os.path.exists(template_path):
        return set(), []

    template_entries, template_header = parse_po(template_path)
    template_keys = set(template_entries)
    require(template_header, '{} missing gettext header'.format(template_path), errors)
    require(bool(template_keys), '{} contains no msgid entries'.format(template_path), errors)

    po_files = [
        filename for filename in sorted(os.listdir(TRANSLATION_SOURCES))
        if filename.endswith('.po')
    ] if os.path.isdir(TRANSLATION_SOURCES) else []
    require(bool(po_files), 'no .po files found in {}'.format(TRANSLATION_SOURCES), errors)

    languages = []
    for filename in po_files:
        language = filename[:-3]
        languages.append(language)
        path = os.path.join(TRANSLATION_SOURCES, filename)
        entries, header_seen = parse_po(path)
        keys = set(entries)
        missing = sorted(template_keys - keys)
        extra = sorted(keys - template_keys)
        empty = sorted(key for key, value in entries.items() if not value.strip())

        require(header_seen, '{} missing gettext header'.format(path), errors)
        require(not missing, '{} missing msgids: {}'.format(path, ', '.join(missing)), errors)
        require(not extra, '{} has extra msgids: {}'.format(path, ', '.join(extra)), errors)
        require(not empty, '{} has empty msgstr values: {}'.format(path, ', '.join(empty)), errors)

    return set(languages), sorted(languages)


def validate_runtime_mo_files(languages, errors):
    require(os.path.isdir(RUNTIME_TRANSLATIONS),
            'missing runtime translation directory: {}'.format(RUNTIME_TRANSLATIONS), errors)
    if not os.path.isdir(RUNTIME_TRANSLATIONS):
        return

    mo_languages = set(
        filename[:-3] for filename in os.listdir(RUNTIME_TRANSLATIONS)
        if filename.endswith('.mo')
    )
    missing = sorted(languages - mo_languages)
    extra = sorted(mo_languages - languages)
    require(not missing, 'translations/ missing .mo files for: {}'.format(', '.join(missing)), errors)
    require(not extra, 'translations/ has extra .mo files for: {}'.format(', '.join(extra)), errors)


def main():
    errors = []
    languages, ordered_languages = validate_po_sources(errors)
    validate_runtime_mo_files(languages, errors)

    if errors:
        print('Translation validation failed:')
        for error in errors:
            print(' - {}'.format(error))
        return 1

    print('Translation validation passed.')
    print('Languages: {}'.format(len(ordered_languages)))
    print('Strings: {}'.format(len(parse_po(os.path.join(TRANSLATION_SOURCES, TEMPLATE))[0])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
