# Decisions

Local docs:

- `README.md` and `_docs/` are local-only handoff notes.
- They are excluded through `.git/info/exclude`, not `.gitignore`, so the repo does not advertise them.

Plugin boundaries:

- Keep `__init__.py` lightweight. GUI imports belong in `ui.py` or later imports from `config_widget()` so command-line Calibre utilities can inspect plugin metadata without loading Qt.
- Use Calibre APIs where they exist: `InterfaceActionBase`, `InterfaceAction`, `JSONConfig`, `qt.core`, `calibre.browser`, and Calibre database methods.
- Preserve the installed import name `calibre_plugins.Goodreads_character_and_settings`.

Goodreads extraction:

- The active parser uses Goodreads `__NEXT_DATA__` JSON entities rather than scraping visible labels.
- Accept only entity types that match the requested column: character entities for Characters, place/places/setting entities for Settings.
- URL checks are used when an entity has a link so character/place entities do not bleed into the wrong destination.

Country and settings behavior:

- Country and region normalization is user-data driven. Defaults are bundled in `resources/`, then copied to human-editable JSON files under Calibre's plugin config directory.
- Canonical Countries output should be deduplicated and separate from Settings output.
- Region values may remain in Settings when configured, while still mapping to a canonical country.
- Title-sort articles left behind after country stripping, such as `The` in `The United States`, should not become settings.

Field writes:

- Existing destination values are preserved and merged with imported values.
- Tags and Calibre multiple-value fields receive list payloads.
- Scalar custom fields receive comma-separated string payloads.
- Do not write empty payloads unless the user explicitly enabled `write_empty_to_custom_fields`; even then, it applies only to custom fields, not tags.

Progress behavior:

- Background workers report progress per processed book.
- GUI-side job accounting is per batch. Failed jobs count the whole batch as failed; failed per-book results count individually.

Packaging:

- Release zips must include plugin modules, `images/`, `resources/`, and runtime `translations/`.
- Release zips must not include `_dev_tools/` or development-only helpers.

Migration:

- User JSON schema support currently includes legacy migration. `database_update.py` notes that v1 user JSON migration can be removed after May 2027.
- Missing ISO codes are inferred only while migrating pre-v2 user JSON data. Current schema data should preserve intentionally blank ISO values.

Testing:

- Keep smoke tests runnable outside a full Calibre install by faking the minimal Calibre modules they need.
- Resource and translation validators are part of the effective test surface, not optional polish.

Python:

- Use `py -3.12` or the workspace venv where available.
- BeautifulSoup is an expected dependency in the target Calibre runtime and local Python 3.12 environment.

Documentation:

- Do not use noisy `AGENT TELEMETRY` style labels in source.
- Prefer concise comments explaining contracts, invariants, and edge cases.
