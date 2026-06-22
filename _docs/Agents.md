# Local Agent Notes

This file is local-only. It is excluded through `.git/info/exclude` and should not be committed or uploaded with the repository.

## Local Docs Reference

Check the local `_docs/` files before making broad changes or continuing an older thread:

- `_docs/PROJECT_CONTEXT.md`: project purpose, current architecture direction, editing habits, and test command reminders.
- `_docs/ARCHITECTURE.md`: current module responsibilities, extraction and normalization flow, user JSON behavior, and test harness notes.
- `_docs/DECISIONS.md`: durable local decisions about Calibre boundaries, Goodreads extraction, field writes, packaging, migration, testing, and documentation style.
- `_docs/PLANS.md`: testing, documentation, and stabilization plans.
- `_docs/TASKS.md`: current todo list and watch points.
- `_docs/CODEX_HANDOFF.md`: preferred commands, test shape, sandbox notes, dirty-tree expectations, and local-only doc notes.

## Calibre Plugin Conventions

Prefer Calibre's plugin APIs, bundled third-party libraries, and conventions over generic Python or Qt patterns when Calibre provides an appropriate tool.

Use Calibre-facing APIs at plugin boundaries, including:

- `qt.core` imports instead of direct PyQt or PySide imports.
- `calibre.utils.config.JSONConfig` for plugin preferences.
- `calibre.browser` for Goodreads fetches from worker jobs.
- `InterfaceActionBase` and `InterfaceAction` for plugin lifecycle and UI integration.
- Calibre job manager APIs for background work.
- Calibre database APIs such as `new_api.set_field` when available, with compatibility fallbacks for older APIs.

When a third-party library is bundled with Calibre, treat it as part of the preferred Calibre runtime toolset for plugin code. BeautifulSoup is the current parser dependency for Goodreads HTML and JSON payload discovery.

Plain Python remains appropriate for focused domain code such as parser helpers, normalization logic, migration helpers, and other modules that do not need direct Calibre UI integration.

## Project-Specific Boundaries

- Keep `__init__.py` import-light so Calibre command-line utilities can inspect plugin metadata without loading Qt.
- Keep GUI action behavior in `ui.py`.
- Keep GUI-side selection, job orchestration, database writes, and refresh behavior in `main.py`.
- Keep network fetch and extraction execution in `worker_process.py`.
- Keep parser, formatter, country, and field-payload logic in `common.py`.
- Keep user JSON defaults, schema normalization, and read/write helpers in `settings_data.py`.
- Keep version-gated migration in `database_update.py`.

## Comment And Documentation Style

Use comments to document constraints that are easy to break during refactors, not to narrate obvious code.

Prefer these headings in module or class docstrings when they genuinely help:

- `Maintenance notes`
- `Type constraints`
- `Invariants`
- `Refactor warning`

Avoid labels such as `AGENT_HINT` or `AGENT_TELEMETRY`. They are noisy in normal source files and do not describe runtime behavior.

## When To Add Documentation

Add module or class documentation when code depends on:

- Calibre API behavior that is not obvious from the call site.
- Plugin import boundaries or deferred imports.
- Parser input shapes from Goodreads HTML and the `__NEXT_DATA__` JSON payload.
- Progress counters where the denominator must match real writes.
- Matching or normalization rules where a simpler-looking change would broaden or narrow matches.
- User JSON schema migration behavior.

Use inline comments for load-bearing details only:

- A line looks inefficient but protects a known edge case.
- A parser workaround handles a specific source shape.
- A fallback order is intentional because earlier options preserve more information or compatibility.

## When Not To Add Documentation

Do not add comments that merely restate the code.

Avoid broad claims like:

- "This simply handles..."
- "This easily manages..."
- "Optimize this later..."

Do not add complexity notes unless the logic is dense, performance-sensitive, or likely to be mistaken during refactoring.

## User Storage Notes

User-editable data is stored under Calibre's config directory:

- `plugins/Goodreads_character_and_settings/countries.json`
- `plugins/Goodreads_character_and_settings/regions.json`
- `plugins/Goodreads_character_and_settings/autodelete.json`

These files are seeded from bundled resources and should not be confused with repository resources. Repository resource files provide defaults; user JSON files are runtime data.
