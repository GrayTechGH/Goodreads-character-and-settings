"""Compile the plugin's UTF-8 PO catalogs without external gettext tools."""

import struct
from pathlib import Path

from validate_translations import ROOT, read_po_catalog


def compile_catalog(catalog):
    items = sorted((key.encode('utf-8'), value.encode('utf-8')) for key, value in catalog.items())
    count = len(items)
    offset = 28 + 16 * count
    original = bytearray()
    translated = bytearray()
    original_table = []
    translated_table = []
    for key, value in items:
        original_table.append((len(key), offset + len(original)))
        original.extend(key + b'\0')
    offset += len(original)
    for key, value in items:
        translated_table.append((len(value), offset + len(translated)))
        translated.extend(value + b'\0')
    header = struct.pack('<7I', 0x950412de, 0, count, 28, 28 + 8 * count, 0, 0)
    tables = b''.join(struct.pack('<2I', *entry) for entry in original_table + translated_table)
    return header + tables + original + translated


def main():
    root = Path(ROOT)
    for source in sorted((root / '_dev_tools' / 'translations').glob('*.po')):
        destination = root / 'translations' / (source.stem + '.mo')
        destination.write_bytes(compile_catalog(read_po_catalog(source)))
    print('Compiled {} catalogs.'.format(len(list((root / 'translations').glob('*.mo')))))


if __name__ == '__main__':
    main()
