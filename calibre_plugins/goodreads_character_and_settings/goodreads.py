import json
import re
from collections import OrderedDict
from html import unescape
from urllib.parse import quote
from urllib.request import Request, urlopen

USER_AGENT = (
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/124.0 Safari/537.36'
)


def fetch_book_page(goodreads_id, timeout=25):
    url = f'https://www.goodreads.com/book/show/{quote(str(goodreads_id))}'
    req = Request(url, headers={'User-Agent': USER_AGENT})
    with urlopen(req, timeout=timeout) as response:
        return response.read().decode('utf-8', errors='replace')


def extract_characters_and_settings(html):
    text = _clean_html(html)

    characters = _extract_people(text)
    settings = _extract_settings(text)

    if not settings:
        settings = _extract_settings_from_json(html)

    return dedupe(characters), dedupe(settings)


def dedupe(items):
    return [x for x in OrderedDict((item.strip(), 1) for item in items if item and item.strip()).keys()]


def _clean_html(html):
    stripped = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.I | re.S)
    stripped = re.sub(r'<style[^>]*>.*?</style>', ' ', stripped, flags=re.I | re.S)
    stripped = re.sub(r'<[^>]+>', ' ', stripped)
    stripped = unescape(stripped)
    return re.sub(r'\s+', ' ', stripped)


def _extract_people(text):
    # Goodreads generally renders a "Characters" section with comma-separated names.
    return _extract_labeled_list(text, 'Characters')


def _extract_settings(text):
    items = _extract_labeled_list(text, 'Setting')
    if not items:
        items = _extract_labeled_list(text, 'Settings')

    normalized = []
    for raw in items:
        normalized.extend(_normalize_setting_item(raw))
    return normalized


def _extract_labeled_list(text, label):
    patterns = [
        rf'{label}\s*[:\-]\s*(.+?)(?=\s+[A-Z][a-z][^,]{{2,}}\s*[:\-]|$)',
        rf'{label}\s+(.+?)(?=\s+[A-Z][a-z][^,]{{2,}}\s*[:\-]|$)',
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            blob = m.group(1)
            parts = re.split(r'\s*,\s*|\s*;\s*|\s+\|\s+', blob)
            return [p.strip() for p in parts if p.strip()]
    return []


def _extract_settings_from_json(html):
    settings = []
    for m in re.finditer(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, flags=re.I | re.S):
        data = m.group(1).strip()
        try:
            obj = json.loads(data)
        except Exception:
            continue
        for item in _walk_json(obj):
            if isinstance(item, dict):
                key = (item.get('name') or '').lower()
                if 'setting' in key and item.get('value'):
                    settings.extend(_normalize_setting_item(str(item['value'])))
            if isinstance(item, str) and 'united states' in item.lower() and '(' in item and ')' in item:
                settings.extend(_normalize_setting_item(item))
    return settings


def _walk_json(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk_json(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_json(item)
    else:
        yield obj


def _normalize_setting_item(item):
    item = item.strip(' ,')
    if not item:
        return []

    # Example input:
    # Washington, D.C. (United States), Pennsylvania (United States)
    # Output:
    # Washington, D.C., Pennsylvania, United States
    matches = re.findall(r'([^,()]+?)\s*\(([^()]+)\)', item)
    if matches:
        places = [m[0].strip() for m in matches]
        countries = dedupe([m[1].strip() for m in matches])
        return [', '.join(places + countries)]

    if '(' in item and ')' in item:
        base = re.sub(r'\([^)]*\)', '', item).strip(' ,')
        country_matches = re.findall(r'\(([^)]+)\)', item)
        if country_matches:
            return [', '.join([base] + dedupe(country_matches))]

    return [item]
