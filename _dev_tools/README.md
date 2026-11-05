Development-only helpers.

Do not include this folder in the released Calibre plugin zip. The release
payload should contain only the plugin modules, import marker, license, and
the `images`, `resources`, and runtime `translations` folders.

Fetch mitigation checks (Calibre must be on PATH):

```powershell
python _dev_tools\run_calibre_check.py _dev_tools\run_tests.py
python _dev_tools\run_calibre_check.py _dev_tools\qa_fetch_runtime.py gui
python _dev_tools\run_calibre_check.py _dev_tools\qa_release_runtime.py
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

Minimum supported Calibre is **5.40.0**. Actual Windows portable runtimes were
checked at 5.0.0, 5.39.1, and 5.40.0. Version 5.0 lacks `qt.core`; both earlier
versions lack `random_common_chrome_user_agent`. Calibre 5.40 passed the full
59-test suite, actual release ZIP installation/settings save-and-reopen/debug
dialog checks, and background-job progress/failure/cancellation/lock recovery.
The corrected ZIP refuses installation on 5.0 and 5.39.1. These checks use no
user library and do not establish visual layout quality or live network access.

To select an older runtime, set both variables before running the commands:

```powershell
$env:CALIBRE_DEBUG_EXECUTABLE = 'C:\path\to\Calibre\calibre-debug.exe'
$env:QT_QPA_PLATFORM = 'minimal'
```

The runner prepends that executable's directory to PATH so subprocesses also
use the selected version. Qt 5 uses `minimal`: its `offscreen` platform hung
while constructing QApplication in this environment. The default remains
`offscreen` for the installed current Calibre. `qa_release_runtime.py` exercises
the actual top-level release ZIP through Calibre's plugin loader, checks source
parity, four settings tabs, saved pacing, hidden Books/Job, the debug dialog,
the real random user-agent API, and the minimum shown in About.

Translation maintenance:

```powershell
python _dev_tools\compile_translations.py
python _dev_tools\validate_translations.py
```

Add literal `_('message')` calls before applying `.format(...)`. Add each new
message to `translations/goodreads_cs.pot` and every language `.po` under this
development folder, then compile the runtime `translations/*.mo` files.
The validator checks source/template coverage, untranslated literals at owned
UI/error boundaries, message constants, placeholders, Unicode PO parsing,
duplicates/fuzzy entries, and exact compiled/source catalog parity. Debug logs
and external exception details are not translated. Dynamic text still needs
review because static checks cannot prove its translation path.
