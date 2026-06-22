# Project Context

Core domain:

- Calibre interface action plugin: `Goodreads character and settings`.
- Imports Characters, Settings, and Countries data from Goodreads book pages for selected Calibre library rows.
- Uses each selected book's Goodreads identifier, fetches `https://www.goodreads.com/book/show/<id>`, extracts entity data from the page's `__NEXT_DATA__` JSON payload, and writes normalized values back to Calibre tags or user-selected custom fields.
- Settings are split into display places and canonical countries. Country and region normalization is driven by editable user JSON files seeded from bundled defaults.
- Users can configure destination fields, country naming/localization behavior, region retention, query pacing, job batch size, and auto-delete rules.

Important editing habits:

- Keep changes narrowly scoped. This code has been split in phases and should stay easy to bisect.
- Use Python 3.12 for local checks when possible. In this workspace, the local venv command is usually `.\.venv\Scripts\python.exe`.
- There may be unrelated dirty files in the worktree. Do not revert them without explicit user approval.
- Prefer Calibre plugin APIs at plugin boundaries: `InterfaceActionBase`, `InterfaceAction`, `JSONConfig`, `qt.core`, Calibre job manager, Calibre browser, and Calibre database APIs.
- Keep imports that would load GUI libraries out of `__init__.py` unless Calibre expects them there.
- Preserve the plugin import package name `calibre_plugins.Goodreads_character_and_settings`; Calibre depends on it for installed-plugin imports.
- Do not include `_dev_tools/` or standalone development helpers in release zips.

Useful local commands:

- Run smoke tests: `py -3.12 _dev_tools\run_tests.py`
- Compile key modules: `py -3.12 -m py_compile __init__.py ui.py main.py worker_process.py common.py config.py settings_data.py database_update.py about.py`
- Validate bundled resources: `py -3.12 _dev_tools\validate_resources.py`
- Validate translations: `py -3.12 _dev_tools\validate_translations.py`

Documentation style:

- Prefer useful comments at module boundaries, parser normalization boundaries, and load-bearing edge cases.
- Avoid `AGENT_*` labels in code comments.
- Use headings such as `Maintenance notes`, `Type constraints`, `Invariants`, and `Refactor warning` where a docstring needs future-agent guidance.
