"""Regression checks for source coverage, Unicode, and compiled catalog parity."""

import gettext
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

DEV = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEV))
import validate_translations as validator
from compile_translations import compile_catalog


class TranslationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def write_po(self, path, messages):
        catalog = {'': 'Content-Type: text/plain; charset=UTF-8\nLanguage: fr\n', **messages}
        path.write_text('\n\n'.join('msgid {}\nmsgstr {}'.format(json.dumps(k, ensure_ascii=False),
                                                               json.dumps(v, ensure_ascii=False))
                                    for k, v in catalog.items()), encoding='utf-8')
        return catalog

    def test_utf8_quotes_multiline_and_compilation_round_trip(self):
        path = self.root / 'fr.po'
        catalog = self.write_po(path, {'Read {}': 'Lire {}', 'Résumé\n"quote"': '日本語\n"café"',
                                      'Waiting': 'انتظار'})
        parsed = validator.read_po_catalog(path)
        self.assertEqual(catalog, parsed)
        compiled = gettext.GNUTranslations(io.BytesIO(compile_catalog(parsed)))
        self.assertEqual(parsed, compiled._catalog)
        self.assertEqual('Lire livre', compiled.gettext('Read {}').format('livre'))
        path.write_text('msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
                        'msgid "Long "\n"message"\nmsgstr "Un "\n"message"\n', encoding='utf-8')
        self.assertEqual('Un message', validator.parse_po(path)[0]['Long message'])

    def test_duplicate_and_fuzzy_entries_are_rejected(self):
        path = self.root / 'bad.po'
        for content in ('msgid "A"\nmsgstr "B"\nmsgid "A"\nmsgstr "C"\n',
                        '#, fuzzy\nmsgid "A"\nmsgstr "B"\n'):
            path.write_text(content, encoding='utf-8')
            with self.assertRaises(ValueError):
                validator.parse_po(path)

    def test_literals_are_extracted_before_formatting(self):
        errors = []
        messages = validator.source_messages(
            'MESSAGE = _("Book {}")\nlabel.setText(_("A"))\n'
            'raise RuntimeError(_("Error: {}").format(detail))\n', 'sample.py', errors)
        self.assertEqual({'Book {}', 'A', 'Error: {}'}, messages)
        self.assertEqual([], errors)

    def test_unwrapped_errors_constants_and_ui_strings_are_rejected(self):
        cases = [
            'raise RuntimeError("Untranslated")',
            'raise Exception("Untranslated")',
            'raise RuntimeError("Error: {}".format(detail))',
            'raise ValueError(f"Error {detail}")',
            'raise ValueError("Error: " + detail)',
            'MESSAGE = "Untranslated"\nraise RuntimeError(MESSAGE)',
            'ERROR_MESSAGES = {404: "Not found"}',
            'QLabel("Untranslated")',
            'widget.setWindowTitle("Untranslated")',
            'QMessageBox.warning(parent, _("Title"), "Untranslated")',
            '_("Error: {}".format(detail))',
            '_(f"Error {detail}")',
        ]
        for source in cases:
            with self.subTest(source=source):
                errors = []
                validator.source_messages(source, 'sample.py', errors)
                self.assertTrue(errors)
                self.assertTrue(all('sample.py:' in error for error in errors))

    def test_template_source_gap_is_detected(self):
        (self.root / 'source.py').write_text('label.setText(_("New label"))', encoding='utf-8')
        sources = self.root / 'catalogs'
        sources.mkdir()
        self.write_po(sources / validator.TEMPLATE, {'Old label': ''})
        errors = []
        with patch.object(validator, 'ROOT', str(self.root)), patch.object(validator, 'TRANSLATION_SOURCES', str(sources)):
            validator.validate_source_coverage(errors)
        self.assertTrue(any('New label' in error for error in errors))

    def test_placeholder_mismatch_is_detected(self):
        self.write_po(self.root / validator.TEMPLATE, {'Failed {}': ''})
        self.write_po(self.root / 'fr.po', {'Failed {}': 'Échec'})
        errors = []
        with patch.object(validator, 'TRANSLATION_SOURCES', str(self.root)):
            validator.validate_po_sources(errors)
        self.assertTrue(any('mismatched placeholders' in error for error in errors))
        self.assertNotEqual(validator.placeholders('{count}'), validator.placeholders('{other}'))

    def test_missing_stale_and_corrupt_mo_are_detected(self):
        runtime = self.root / 'runtime'
        runtime.mkdir()
        catalog = self.write_po(self.root / 'fr.po', {'New label': 'Nouveau libellé'})
        with patch.object(validator, 'TRANSLATION_SOURCES', str(self.root)), patch.object(validator, 'RUNTIME_TRANSLATIONS', str(runtime)):
            errors = []
            validator.validate_runtime_mo_files({'fr'}, errors)
            self.assertTrue(errors)
            (runtime / 'fr.mo').write_bytes(compile_catalog({'': catalog[''], 'Old label': 'Ancien libellé'}))
            errors = []
            validator.validate_runtime_mo_files({'fr'}, errors)
            self.assertTrue(any('differs' in error for error in errors))
            (runtime / 'fr.mo').write_bytes(b'broken')
            errors = []
            validator.validate_runtime_mo_files({'fr'}, errors)
            self.assertTrue(any('invalid .mo' in error for error in errors))
            (runtime / 'fr.mo').write_bytes(compile_catalog(catalog))
            errors = []
            validator.validate_runtime_mo_files({'fr'}, errors)
            self.assertEqual([], errors)

    def test_all_current_source_messages_exist_in_every_runtime_catalog(self):
        errors = []
        messages = validator.validate_source_coverage(errors)
        self.assertEqual([], errors)
        for path in sorted(Path(validator.RUNTIME_TRANSLATIONS).glob('*.mo')):
            with path.open('rb') as stream:
                catalog = gettext.GNUTranslations(stream)._catalog
            self.assertTrue(messages <= set(catalog), path.name)


if __name__ == '__main__':
    unittest.main()
