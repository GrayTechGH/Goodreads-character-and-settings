# Codex Handoff

This repository is a Calibre plugin named `Goodreads character and settings`.

## First Things To Know

- The installed plugin import package is `calibre_plugins.Goodreads_character_and_settings`.
- The Calibre wrapper class is in `__init__.py`; the GUI action class is in `ui.py`.
- The main import flow is GUI collection and writes in `main.py`, background fetch/extract in `worker_process.py`, and parsing/normalization in `common.py`.
- Configuration UI and persistent preferences live in `config.py`.
- User-editable country, region, and auto-delete JSON handling lives in `settings_data.py`.
- Schema/version migration lives in `database_update.py`.

## Preferred Commands

- Run smoke tests: `py -3.12 _dev_tools\run_tests.py`
- Compile modules: `py -3.12 -m py_compile __init__.py ui.py main.py worker_process.py common.py config.py settings_data.py database_update.py about.py`
- Validate resources: `py -3.12 _dev_tools\validate_resources.py`
- Validate translations: `py -3.12 _dev_tools\validate_translations.py`

If `py -3.12` is unavailable, try `.\.venv\Scripts\python.exe` with the same arguments.

## Current Test Shape

The smoke test suite fakes enough Calibre modules to run key logic without launching Calibre. It currently checks:

- Bundled resource JSON validity.
- Release zip contents and development-helper exclusions.
- Translation catalog coverage for selected UI strings.
- Country-name defaults and localization behavior.
- First-run user JSON creation.
- Malformed user JSON fallback and repair flags.
- ISO inference rules for legacy schema data.
- Common cleanup/merge behavior.
- Article-only setting removal after country stripping.

## Sandbox Notes

This workspace sometimes needs escalated PowerShell reads even for ordinary file inspection. If simple reads fail with `CreateProcessAsUserW failed: 5`, retry the same narrow command with approval rather than changing the task.

## Dirty Tree Expectations

There may be unrelated dirty files. Do not revert user changes. Keep documentation edits in `_docs/` unless the user asks for public docs or source comments.

## Local-Only Documentation

These docs are intended as local handoff notes. The templates say `_docs/` and `README.md` are excluded through `.git/info/exclude`; confirm that before assuming they are commit-bound or release-bound.
