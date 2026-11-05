"""Install and exercise the actual release ZIP in a disposable Calibre profile."""

import json
import os
from pathlib import Path
import zipfile


def main():
    if not os.environ.get('CALIBRE_CONFIG_DIRECTORY'):
        raise SystemExit('Use run_calibre_check.py with a disposable profile.')
    root = Path(__file__).resolve().parent.parent
    package = root / 'Goodreads-character-and-settings.zip'
    # Import through Calibre's installed-plugin loader, not a source-directory shim.
    from calibre.customize.ui import add_plugin
    from calibre.constants import numeric_version
    plugin = add_plugin(str(package))
    with plugin:
        from qt.core import QApplication, QLabel
        from calibre_plugins.Goodreads_character_and_settings import config, ui
        from calibre_plugins.Goodreads_character_and_settings.about import build_about_text
        from calibre_plugins.Goodreads_character_and_settings.debug import GoodreadsDebugDialog
        from calibre_plugins.Goodreads_character_and_settings.worker_process import random_goodreads_user_agent

    app = QApplication.instance() or QApplication([])
    widget = config.ConfigWidget(custom_fields=[('#characters', 'Characters')])
    assert widget.tabs.count() == 4
    assert not hasattr(widget, 'max_books_per_job')
    assert not any('Books/Job' in label.text() for label in widget.findChildren(QLabel))
    widget.query_interval_seconds.setValue(17)
    widget.save_settings()
    reopened = config.ConfigWidget()
    assert reopened.query_interval_seconds.value() == 17
    debug = GoodreadsDebugDialog(None)
    assert debug.simulated_error.count() > 1
    assert ui.InterfacePlugin.popup_type is not None
    assert random_goodreads_user_agent()
    assert plugin.minimum_calibre_version == (5, 40, 0)
    assert '5.40.0' in build_about_text()
    with zipfile.ZipFile(package) as archive:
        for path in root.glob('*.py'):
            assert archive.read(path.name) == path.read_bytes(), path.name
    print(json.dumps({'calibre': numeric_version, 'release_zip_installed': True,
                      'settings_tabs': widget.tabs.count(), 'settings_reopened': True,
                      'debug_dialog': True, 'random_user_agent': True,
                      'minimum_calibre': plugin.minimum_calibre_version,
                      'library_opened': False}), flush=True)
    widget.close()
    reopened.close()
    debug.close()
    app.processEvents()


if __name__ == '__main__':
    main()
