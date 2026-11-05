#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


from __future__ import print_function

import os
import sys
import ast
import gettext
import struct
from collections import Counter
from pathlib import Path
from string import Formatter


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANSLATION_SOURCES = os.path.join(ROOT, '_dev_tools', 'translations')
RUNTIME_TRANSLATIONS = os.path.join(ROOT, 'translations')
TEMPLATE = 'goodreads_cs.pot'


def require(condition, message, errors):
    if not condition:
        errors.append(message)


def unescape_po_string(value):
    return ast.literal_eval('"' + value + '"')


def read_po_catalog(path):
    entries = {}
    current_id = None
    current_str = None
    mode = None

    def save_entry():
        if current_id is not None:
            if current_str is None:
                raise ValueError('{}: missing msgstr for {!r}'.format(path, current_id))
            if current_id in entries:
                raise ValueError('{}: duplicate msgid {!r}'.format(path, current_id))
            entries[current_id] = current_str

    with open(path, 'r', encoding='utf-8') as f:
        for line_number, raw_line in enumerate(f, 1):
            line = raw_line.strip()
            if line.startswith('#,') and 'fuzzy' in line:
                raise ValueError('{}:{} fuzzy translation'.format(path, line_number))
            if not line or line.startswith('#'):
                continue

            if line.startswith('msgid '):
                save_entry()
                raw_value = line[6:].strip()
                current_id = unescape_po_string(raw_value[1:-1])
                current_str = None
                mode = 'id'
                continue

            if line.startswith('msgstr '):
                raw_value = line[7:].strip()
                current_str = unescape_po_string(raw_value[1:-1])
                mode = 'str'
                continue

            if line.startswith('"') and line.endswith('"'):
                value = unescape_po_string(line[1:-1])
                if mode == 'id' and current_id is not None:
                    current_id += value
                elif mode == 'str' and current_id is not None:
                    current_str = (current_str or '') + value
                continue

            raise ValueError('{}:{} unsupported .po syntax: {}'.format(path, line_number, raw_line.rstrip()))

    save_entry()
    return entries


def parse_po(path):
    catalog = read_po_catalog(path)
    header_seen = '' in catalog
    catalog.pop('', None)
    return catalog, header_seen


def placeholders(text):
    return Counter((field, conversion, spec) for _, field, spec, conversion in Formatter().parse(text) if field is not None)


def source_messages(source, filename, errors):
    """Extract literal gettext calls and check owned exception/UI boundaries.

    This is deliberately static: external exception text and dynamically built
    widget contents cannot be proven translated. Debug/diagnostic logs are not
    UI sinks. Module message constants and dictionaries must be translated.
    """
    tree = ast.parse(source, filename=filename)
    bindings = {target.id: node.value for node in tree.body if isinstance(node, ast.Assign)
                for target in node.targets if isinstance(target, ast.Name)}
    messages = set()

    def translated(node):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == '_':
                return True
            if isinstance(node.func, ast.Attribute) and node.func.attr == 'format':
                return translated(node.func.value)
        return False

    def check(node, context):
        if isinstance(node, ast.Name) and node.id in bindings:
            return check(bindings[node.id], context)
        if isinstance(node, (ast.List, ast.Tuple)):
            for item in node.elts:
                check(item, context)
        elif isinstance(node, ast.Dict):
            for item in node.values:
                check(item, context)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value:
            errors.append('{}:{} untranslated {}: {!r}'.format(filename, node.lineno, context, node.value))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'format':
            if not translated(node):
                check(node.func.value, context)
        elif isinstance(node, ast.JoinedStr):
            errors.append('{}:{} untranslated {} (f-string)'.format(filename, node.lineno, context))
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            check(node.left, context)
            check(node.right, context)

    methods = {'setWindowTitle': (0,), 'setText': (0,), 'setToolTip': (0,), 'setStatusTip': (0,),
               'setPlaceholderText': (0,), 'setSuffix': (0,), 'addItem': (0,), 'addItems': (0,),
               'addRow': (0,), 'addTab': (1,), 'setHorizontalHeaderLabels': (0,), 'show_status': (0,)}
    constructors = {'QLabel', 'QPushButton', 'QCheckBox', 'QGroupBox'}
    for name, value in bindings.items():
        if name.endswith(('_MESSAGE', '_MESSAGES')):
            check(value, 'message constant')
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            name = node.func.id
            if name == '_':
                if len(node.args) != 1 or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
                    errors.append('{}:{} gettext requires an unformatted string literal'.format(filename, node.lineno))
                else:
                    messages.add(node.args[0].value)
            elif (name.endswith('Error') or name in ('Exception', 'BaseException')) and node.args:
                index = 1 if name == 'GoodreadsHttpError' else 0
                if len(node.args) > index:
                    check(node.args[index], 'exception message')
            elif name in constructors and node.args:
                check(node.args[0], 'UI label')
        elif isinstance(node.func, ast.Attribute):
            indices = methods.get(node.func.attr, ())
            if isinstance(node.func.value, ast.Name) and node.func.value.id == 'QMessageBox':
                if node.func.attr in ('warning', 'information', 'critical', 'question'):
                    indices = (1, 2)
            for index in indices:
                if index < len(node.args):
                    check(node.args[index], 'UI text')
    return messages


def validate_source_coverage(errors):
    messages = set()
    for path in sorted(Path(ROOT).glob('*.py')):
        messages.update(source_messages(path.read_text(encoding='utf-8-sig'), str(path), errors))
    template, _ = parse_po(os.path.join(TRANSLATION_SOURCES, TEMPLATE))
    for message in sorted(messages - set(template)):
        errors.append('translation template missing source msgid: {!r}'.format(message))
    return messages


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
        for key, value in entries.items():
            try:
                require(placeholders(key) == placeholders(value), '{} has mismatched placeholders for {!r}'.format(path, key), errors)
            except ValueError as error:
                errors.append('{} invalid format string {!r}: {}'.format(path, key, error))

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
    for language in sorted(languages & mo_languages):
        source = read_po_catalog(os.path.join(TRANSLATION_SOURCES, language + '.po'))
        try:
            with open(os.path.join(RUNTIME_TRANSLATIONS, language + '.mo'), 'rb') as stream:
                runtime = gettext.GNUTranslations(stream)._catalog
            require(runtime == source, '{}.mo differs from its .po source; recompile it'.format(language), errors)
        except (OSError, UnicodeError, ValueError, EOFError, struct.error) as error:
            errors.append('{} invalid .mo: {}'.format(language, error))


def main():
    errors = []
    try:
        languages, ordered_languages = validate_po_sources(errors)
        validate_runtime_mo_files(languages, errors)
        messages = validate_source_coverage(errors)
    except (OSError, ValueError, SyntaxError, UnicodeError) as error:
        errors.append(str(error))

    if errors:
        print('Translation validation failed:')
        for error in errors:
            print(' - {}'.format(error))
        return 1

    print('Translation validation passed.')
    print('Languages: {}'.format(len(ordered_languages)))
    print('Strings: {}'.format(len(parse_po(os.path.join(TRANSLATION_SOURCES, TEMPLATE))[0])))
    print('Source strings: {}'.format(len(messages)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
