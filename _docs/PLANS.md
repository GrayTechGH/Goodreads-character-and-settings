# Plans

Testing plan:

- Keep `_dev_tools\run_tests.py` as the main local smoke check.
- Add focused tests around parser and formatter behavior when changing `common.py`.
- Add fake-Calibre tests for GUI-side field payload application only when changing `main.py` write behavior.
- Run translation/resource validators before release packaging changes.

Documentation plan:

- Keep these `_docs/` files aligned with the actual plugin shape after each broad change.
- Add source comments only around Calibre API contracts, user JSON migration edges, and parser/normalization rules that are easy to simplify incorrectly.
- If release/build steps are formalized later, add a dedicated local release checklist rather than burying packaging notes in architecture docs.

Stabilization plan:

- Watch Goodreads page structure. If `__NEXT_DATA__` changes, update extraction in `common.py` with fixtures that cover the new shape.
- Keep user JSON schemas backward compatible until the documented migration removal date.
- Preserve compatibility paths for older Calibre database APIs unless the minimum Calibre version is intentionally raised.
