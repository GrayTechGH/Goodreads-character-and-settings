# Codex Session Handoff - Goodreads Character And Settings

Reactivation prompt:

```text
We are continuing from this handoff. Read this document first, inspect the current repo state, verify what still applies, and continue from the next steps without assuming the old chat context is available.
```

## Repo And Branch

- Repo: `C:\Users\Graham\Documents\Programming\VSCode\Goodreads-character-and-settings\Goodreads-character-and-settings-1`
- Branch: `Development-1.1.2`
- Remote tracking branch: `origin/Development-1.1.2`
- Worktree status at handoff creation: clean according to `git status --short`.

## Current Goal

The immediate goal was to prepare this repo/session for safe Codex history archival by creating a durable handoff document. The broader project goal remains maintaining the Calibre plugin `Goodreads character and settings`, which imports Characters, Settings, and Countries from Goodreads pages into selected Calibre library rows.

## What We Already Completed

- Ran `keep-codex-fast` in report-only mode to inspect local Codex state before any archive/maintenance action.
- Confirmed the first local-state inspection made no writes, backups, moves, prunes, or deletes.
- Reviewed existing repo-local project docs under `_docs/`.
- Confirmed `_docs/CODEX_HANDOFF.md` already contains a standing project guide and that a dated session handoff is the better place for this archive point.
- Confirmed the repo worktree appeared clean before adding this handoff.
- Created this dated session handoff under `_docs/codex-handoffs/`.

## Files Touched Or Investigated

Touched:

- `_docs/codex-handoffs/2026-05-20-goodreads-character-settings.md`

Investigated:

- `_docs/TASKS.md`
- `_docs/PROJECT_CONTEXT.md`
- `_docs/ARCHITECTURE.md`
- `_docs/CODEX_HANDOFF.md`
- `_docs/DECISIONS.md`
- `_docs/PLANS.md`
- `_docs/Parsers.md`
- Repo file list via `rg --files`
- Git branch/status via `git status --short --branch` and `git status --short`

Important project files called out by the docs:

- `__init__.py`: Calibre `InterfaceActionBase` wrapper and plugin metadata.
- `ui.py`: GUI action class and menu/toolbar integration.
- `main.py`: GUI-side import orchestration and Calibre field writes.
- `worker_process.py`: background Goodreads fetching and extraction.
- `common.py`: extraction, normalization, filtering, and Calibre payload building.
- `config.py`: preferences UI and `JSONConfig` settings.
- `settings_data.py`: bundled/default resources and user-editable JSON handling.
- `database_update.py`: user data/schema migration.
- `_dev_tools/tests/test_smoke.py`: focused fake-Calibre smoke tests.

## Commands And Checks Already Run

Codex local-state inspection:

```powershell
python C:\Users\Graham\.codex\skills\keep-codex-fast\scripts\keep_codex_fast.py
```

Result summary:

- Mode: report-only/read-only.
- Active session size: `0.043 GB`.
- Archived session size: `0.000 GB`.
- Old session candidates: `9`, about `0.016 GB`.
- Largest active sessions: `7.1 MB`, `3.7 MB`, `1.4 MB`, `1.2 MB`, then smaller.
- Logs: `5.5 MB`; rotation skipped because below threshold.
- Stale worktree candidates: `0`.
- Config prune candidates: `0`.
- Windows extended-path entries in thread cwd metadata: `51`.
- Thread metadata repair candidates: `23`.
- No first-user-message preview over `10k` characters.

Repo inspection:

```powershell
git status --short --branch
git status --short
rg --files
Get-ChildItem _docs -Force
Get-Content _docs\TASKS.md
Get-Content _docs\PROJECT_CONTEXT.md
Get-Content _docs\ARCHITECTURE.md
Get-Content _docs\CODEX_HANDOFF.md
Get-Content _docs\DECISIONS.md
Get-Content _docs\PLANS.md
Get-Content _docs\Parsers.md
```

No project test suite was run during this handoff task.

Useful checks from existing repo docs for future work:

```powershell
py -3.12 _dev_tools\run_tests.py
py -3.12 -m py_compile __init__.py ui.py main.py worker_process.py common.py config.py settings_data.py database_update.py about.py
py -3.12 _dev_tools\validate_resources.py
py -3.12 _dev_tools\validate_translations.py
```

If `py -3.12` is unavailable, try the workspace venv command:

```powershell
.\.venv\Scripts\python.exe
```

## Known Errors, Warnings, Or Failing Checks

- `git diff --stat` failed once with `CreateProcessAsUserW failed: 5`, likely the same Windows sandbox/permissions issue already mentioned in `_docs/CODEX_HANDOFF.md`.
- The `keep-codex-fast` report skipped top Node process reporting because its internal PowerShell `Get-Process node ...` command returned a non-zero exit status.
- No source tests were run in this handoff session, so there is no fresh validation beyond read-only inspection and repo status checks.
- `_docs/Parsers.md` currently contains sparse award/risk/test notes rather than detailed parser documentation.

## Open Decisions

- Whether to run normal `keep-codex-fast --apply` after this and any other needed handoffs are created.
- Whether to use optional thread title/preview metadata repair. Normal maintenance reports metadata bloat but does not repair it.
- Whether to archive the 9 old session candidates now or keep some active for continuity.
- Whether to formalize release zip/build steps into a local release checklist.
- Whether to add/update parser fixtures if Goodreads changes its `__NEXT_DATA__` structure.
- Whether/when to remove legacy v1 user JSON migration support after May 2027, as noted in project docs.

## Constraints And Preferences

- Keep changes narrowly scoped and easy to bisect.
- Do not revert unrelated dirty files without explicit user approval.
- Keep `_docs/` local-only unless the user asks for public docs or source comments.
- Preserve the installed Calibre import package name: `calibre_plugins.Goodreads_character_and_settings`.
- Keep Calibre GUI imports out of `__init__.py` unless Calibre explicitly requires them there.
- Use Calibre APIs at plugin boundaries: `InterfaceActionBase`, `InterfaceAction`, `JSONConfig`, `qt.core`, Calibre job manager/browser/database APIs.
- Do not include `_dev_tools/` or standalone development helpers in release zips.
- User data lives under Calibre's config directory, not in the repository.
- Goodreads fetches should remain paced by `query_interval_seconds`; avoid changes that hammer Goodreads.
- Existing destination values should be preserved and merged, not blindly replaced.
- Tags and multiple-value fields should receive list payloads; scalar custom fields should receive comma-separated strings.
- Empty payload writes should remain opt-in through `write_empty_to_custom_fields` and only apply to custom fields.
- Prefer Python 3.12 checks, usually via `py -3.12` or `.\.venv\Scripts\python.exe`.

## Recommended Codex Maintenance Plan

Before applying maintenance:

- Create handoffs for any other active repo chats that may still matter.
- Close Codex, or explicitly use the script's wait-for-exit behavior if applying maintenance while Codex might still be running.
- Keep backup folders local because they may contain private local metadata such as old thread titles and previews.

Normal maintenance command after handoffs are confirmed:

```powershell
python C:\Users\Graham\.codex\skills\keep-codex-fast\scripts\keep_codex_fast.py --apply --archive-older-than-days 10 --worktree-older-than-days 7
```

Optional metadata repair only if thread list/navigation sluggishness is still a problem and the shortened display metadata tradeoff is acceptable:

```powershell
python C:\Users\Graham\.codex\skills\keep-codex-fast\scripts\keep_codex_fast.py --apply --repair-thread-metadata-bloat
```

Normal apply archives and backs up; it does not permanently delete chats, logs, or worktrees. Metadata repair shortens SQLite display title/preview fields but leaves the real rollout transcript in session JSONL.

## Next Steps

1. Inspect `git status --short --branch` in the fresh session and verify this handoff is the only new local change.
2. If continuing product work, read `_docs/PROJECT_CONTEXT.md`, `_docs/ARCHITECTURE.md`, `_docs/DECISIONS.md`, and `_docs/TASKS.md`.
3. Run the smoke/compile/resource/translation checks before making release or broad behavior changes.
4. If changing Goodreads extraction, add focused parser fixtures/tests around the affected `__NEXT_DATA__` shape before editing `common.py`.
5. If changing field write behavior, add focused fake-Calibre tests for payload application before editing `main.py`.
6. If ready to archive Codex history, confirm all important active repo chats have handoffs, then run normal `keep-codex-fast --apply` with Codex closed.
7. After maintenance, rerun the read-only `keep-codex-fast` report and compare active session, archived session, metadata, log, worktree, and config-prune counts.
