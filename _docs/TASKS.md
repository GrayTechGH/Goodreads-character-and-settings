# Tasks

Completed in recent sessions:

- Added local project documentation from the `_docs` templates.
- Documented current Calibre plugin architecture, data flow, migration behavior, and validation commands.

Likely next tasks:

- Add or update parser fixtures when Goodreads changes its `__NEXT_DATA__` structure.
- Add focused tests before altering field write semantics in `main.py` or payload generation in `common.py`.
- Create a repeatable release checklist if packaging is being done manually.
- Consider documenting the release zip build command once it is stable and known.

Watch points:

- `_dev_tools/` must stay out of release zips.
- User data lives under Calibre's config directory, not in the repository.
- User JSON migration code has a TODO to remove v1 support after May 2027.
- Goodreads fetches should remain paced by `query_interval_seconds`; avoid making changes that hammer Goodreads.
- Calibre GUI imports should stay out of `__init__.py`.
