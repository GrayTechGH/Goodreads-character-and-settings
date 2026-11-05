# Architecture

## Plugin Entry Points

- `__init__.py`
  - Defines `GoodreadsCharacterSettingsPlugin`, the Calibre `InterfaceActionBase` wrapper.
  - Keeps GUI imports out of module import time so Calibre command-line utilities can load the plugin metadata without loading Qt.
  - Exposes customization by returning `ConfigWidget` from `config.py`.
  - Declares minimum Calibre 5.40.0, verified with that actual runtime. Earlier 5.x versions lack the required `random_common_chrome_user_agent` API; 5.0 also lacks `qt.core`.

- `ui.py`
  - Defines `InterfacePlugin`, the real GUI action class named by `actual_plugin`.
  - Adds the toolbar action and menu entries for import, customization, and about.
  - Runs `update_database_from_version()` during genesis and clears runtime caches after settings are saved.

- `main.py`
  - Owns the GUI-side import runner.
  - Uses a fixed internal `BOOKS_PER_JOB = 5`. The former Books/Job preference is no longer read or displayed; saved legacy values are ignored without a migration.
  - Collects selected rows, reads Goodreads identifiers and existing destination values, chunks work into Calibre jobs, and applies worker results back through `new_api.set_field` when available.
  - Handles GUI refreshes, tag-view recounts, status messages, and job accounting.

- `worker_process.py`
  - Owns background Goodreads fetch and extraction.
  - Uses Calibre's `browser()` helper, tries the `.xml` detail URL first, and allows one transition to the extensionless URL within a default four-attempt budget.
  - Checks the final Goodreads URL and the titled Book entities' numeric `legacyId` against the requested ID. Valid empty character/settings results succeed immediately; unusable pages remain failures and cannot generate empty field writes.
  - Returns the existing pure data result payloads for the GUI process to write.

- `fetch_policy.py`
  - Coordinates all plugin workers using Calibre's `ExclusiveFile` and versioned JSON state beneath the Calibre cache, keyed by configuration-profile path.
  - Reserves request starts before HTTP access and holds the shared lock through each attempt and cooldown update. Timing sleeps happen outside the lock and recheck state afterward.
  - Enforces the greater of the previous/current configured query intervals, local retry backoff, and shared cooldown. There is no additional between-book sleep.
  - Supports capped exponential backoff with positive jitter, seconds/date `Retry-After` on 429/503, and a 60-second minimum shared cooldown on WAF challenges/403. A longer server delay wins, including responses that also carry a challenge header.
  - Missing state initializes; corrupt, unsupported, or inaccessible state fails without an uncoordinated request. The stable lock file is separate from the atomically replaced state file.
  - Sharing applies to this plugin and configuration profile, not other plugins or profiles. Calibre's HTTP client may follow redirects inside one application attempt; the accepted final URL still must identify the requested book.

## Data Extraction And Normalization

- `common.py` is the shared domain layer for:
  - Cleaning strings and removing markup.
  - Reading/caching country, region, title-sort article, and auto-delete data.
  - Extracting Goodreads entities from the `__NEXT_DATA__` JSON payload with BeautifulSoup and JSON traversal.
  - Filtering extracted values through literal, wildcard, or regex auto-delete rules.
  - Splitting Goodreads settings into normalized Settings and Countries outputs.
  - Building Calibre field payloads that preserve existing values, avoid duplicate writes, and serialize correctly for tags, multiple-value fields, or scalar custom fields.

Important invariants:

- Incoming values are merged with existing destination field values rather than replacing them.
- Tags and multiple-value fields receive lists; scalar custom fields receive comma-separated strings.
- Empty values are skipped unless `write_empty_to_custom_fields` is enabled and the destination is a custom field.
- Countries are canonicalized by editable user data, not hard-coded inside the parser.
- Region values can be preserved in Settings while also mapping to a canonical country in Countries.

## Configuration And User Data

- `config.py`
  - Stores plugin preferences in `JSONConfig('plugins/Goodreads_character_and_settings')`.
  - Builds the Preferences UI with Main, Countries, Regions, and Autodelete tabs.
  - Saves country, region, and auto-delete edits only when the relevant table is dirty.
  - Supports localized country names and can write either English canonical names or selected-language names as country values.

- `settings_data.py`
  - Owns bundled/default resource loading and user-editable JSON file paths under Calibre's config directory.
  - Reads bundled JSON resources from both an unpacked plugin folder and an installed plugin zip.
  - Seeds and repairs user JSON files:
    - `countries.json`
    - `regions.json`
    - `autodelete.json`
  - Tracks schema versions and repair flags consumed by the config UI.

- `database_update.py`
  - Tracks plugin data schema progress through the `database_version` preference.
  - Ensures user JSON files exist for pre-1.0.0 users.
  - Migrates legacy country/region/autodelete payloads for pre-1.0.1 users or when user JSON schema versions lag.

## Resources, Translations, And Packaging

- `resources/default_country_names.json` and `resources/default_country_regions.json` seed country aliases, ISO codes, localized names, and region mappings.
- `translations/*.mo` are runtime gettext catalogs.
- `_dev_tools/translations/*.po` and `_dev_tools/translations/goodreads_cs.pot` are development sources.
- `_dev_tools/` is development-only and must stay out of release plugin zips.
- `images/gr_cs_icon.png` is the toolbar/menu icon loaded through Calibre's `get_icons`.

## Test Harness

- `_dev_tools/run_tests.py` discovers `_dev_tools/tests/test_*.py`.
- `_dev_tools/tests/test_smoke.py` installs fake Calibre modules for focused unit tests outside a full Calibre runtime.
- Current smoke coverage emphasizes resource validation, release zip contents, translation coverage, user JSON defaults/repair, ISO migration behavior, and common value normalization.
