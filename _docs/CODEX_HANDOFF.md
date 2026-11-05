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

- Isolated checks using Calibre's bundled Python/BeautifulSoup: `python _dev_tools\run_calibre_check.py _dev_tools\run_tests.py`
- Isolated Qt/job-manager progress, cancellation, error-reporting, and package check: `python _dev_tools\run_calibre_check.py _dev_tools\qa_fetch_runtime.py gui`
- Optional three-request paced network check: `python _dev_tools\run_calibre_check.py _dev_tools\qa_fetch_runtime.py live`
- These commands use disposable configuration/cache directories. The GUI check installs a temporary test archive only in that disposable profile and opens no library. It uses offscreen Qt and does not establish visual layout quality.

- Run smoke tests: `py -3.12 _dev_tools\run_tests.py`
- Compile modules: `py -3.12 -m py_compile __init__.py ui.py main.py worker_process.py common.py config.py settings_data.py database_update.py about.py`
- Validate resources: `py -3.12 _dev_tools\validate_resources.py`
- Validate translations: `py -3.12 _dev_tools\validate_translations.py`

If `py -3.12` is unavailable, try `.\.venv\Scripts\python.exe` with the same arguments.

## Current Test Shape

Fetch mitigation added 2026-11-04:

- `worker_process.py` uses `.xml` first, one extensionless fallback, and a shared four-attempt default budget. Valid empty metadata succeeds on the first usable response.
- Books/Job has been removed from settings. `main.py` uses `BOOKS_PER_JOB = 5`; any saved `max_books_per_job` value is ignored. The request interval remains configurable and still governs the shared limiter.
- `common.py` validates the final book URL and numeric `legacyId`; conflicting titled Book entities are rejected conservatively.
- `fetch_policy.py` uses Calibre file locks plus cache state shared by workers in the same configuration profile. HTTP attempts, retries, and later books obey query pacing and shared WAF/403/Retry-After cooldowns.
- Runtime cache state has version 1 and fields `last_start`, `interval`, and `cooldown_until`. Do not edit or remove its stable lock file while workers are active. Invalid state reports a coordination failure rather than bypassing pacing.
- New tests use fake clocks for transport policies and actual Calibre subprocesses for concurrency, contention, exception cooldowns, and termination/lock release.
- The isolated runtime harness verifies real Calibre `arbitrary_n` jobs, progress notifications, failure reporting, cancellation during a cooldown, and coordinator recovery. It builds a temporary package containing `fetch_policy.py` and excludes `_dev_tools/` and `_docs/`.
- Runtime QA was performed on Calibre 9.17.0. No version bump, user-library changes, or installation into the user's normal profile were made. The existing top-level release archive has not been rebuilt.
- Final isolated suite: 51 tests passed, including resource validation (47 languages / 249 countries) and translation validation (47 languages / 94 strings). Compilation and `git diff --check` passed. Three paced live requests validated both URL forms and the empty-book case; offscreen job-manager QA passed progress, cancellation, failure reporting, and package checks.

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
