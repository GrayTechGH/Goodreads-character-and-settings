Development-only helpers.

Do not include this folder in the released Calibre plugin zip. The release
payload should contain only the plugin modules plus the `images` and
`resources` folders.

Fetch mitigation checks (Calibre must be on PATH):

```powershell
python _dev_tools\run_calibre_check.py _dev_tools\run_tests.py
python _dev_tools\run_calibre_check.py _dev_tools\qa_fetch_runtime.py gui
python _dev_tools\run_calibre_check.py _dev_tools\qa_fetch_runtime.py live
```

The runner supplies disposable configuration/cache directories. The tests use
Calibre's bundled BeautifulSoup; standalone Python also needs BeautifulSoup.
The `gui` check uses offscreen Qt and real background jobs without opening a
library. It builds/installs a temporary test package in the disposable profile,
checks progress/error reporting, and cancels a worker waiting on a cooldown.
The `live` check makes three Goodreads requests, paced 30 seconds apart, and
prints HTTP success separately from validated/extracted book data. Development
scripts and fixtures must stay out of release archives; include `fetch_policy.py`.
