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

Minimum-version verification, 2026-11-05:

- Corrected `minimum_calibre_version` from the obsolete 0.7.53 declaration to **5.40.0**; plugin version remains 1.3.3. Calibre 5.0 lacks `qt.core`; 5.0 and 5.39.1 lack `random_common_chrome_user_agent`. Official tagged sources and actual isolated Windows portable runtimes confirm this boundary.
- Calibre 5.40 passed all 59 tests, real background-job progress/failure/cancellation/lock recovery, and actual release ZIP installation, all four settings tabs, settings save/reopen, the debug dialog, random user-agent generation, and the corrected About minimum. No user library was opened. These checks do not establish visual appearance or live Goodreads access on the older runtime.
- The rebuilt ZIP is rejected by actual Calibre 5.0 and 5.39.1 installers with the required 5.40.0 version. `_dev_tools/qa_release_runtime.py` is the repeatable installed-archive check. The test runner accepts `CALIBRE_DEBUG_EXECUTABLE`, including matching child executables, and a `QT_QPA_PLATFORM` override. Use `minimal` for the tested Qt 5 runtime; its `offscreen` QApplication initialization hung in this environment.
- The 59-test suite and actual release ZIP settings/debug/API checks also pass on installed Calibre 9.17.0. Compilation and whitespace checks pass. The final release archive contains 63 runtime files and no downloaded compatibility runtimes or development fixtures.
- Upstream boundary: https://github.com/kovidgoyal/calibre/blob/v5.39.1/src/calibre/utils/random_ua.py and https://github.com/kovidgoyal/calibre/blob/v5.40.0/src/calibre/utils/random_ua.py . Official portable runtime downloads: https://download.calibre-ebook.com/ .

Translation follow-up, 2026-11-05:

- Fetch/HTTP errors and coordinator errors use literal gettext wrappers before formatting; `fetch_policy.py` loads plugin translations using the usual fallback pattern. CSV validation and the toolbar label are covered too.
- Added 37 previously missing messages across the template and all 47 PO/MO catalogs. Catalogs now contain 131 message IDs, including all 125 source gettext strings; existing translations and obsolete catalog entries are preserved.
- `_dev_tools/compile_translations.py` rebuilds MO files with the standard-library compiler. `_dev_tools/validate_translations.py` now checks source coverage and owned literal UI/error boundaries, format placeholders, Unicode correctness, duplicate/fuzzy entries, and exact PO/MO parity.
- Eight regression tests cover translation-check failure cases. The full isolated suite now passes 59 tests. Actual ZIP installs passed localization checks in German, Japanese, and Arabic; a German Calibre background job returned a localized error with no field writes.
- The release ZIP was rebuilt from runtime files, including updated MO catalogs and excluding `.gitignore`, `_dev_tools/`, and `_docs/`. Plugin version remains 1.3.3; the verified minimum-version follow-up is recorded above.

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
