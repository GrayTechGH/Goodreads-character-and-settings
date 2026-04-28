#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2026, GrayTechGH'
__docformat__ = 'restructuredtext en'

if False:
    # This is here to keep my python error checker from complaining about
    # the builtin functions that will be defined by the plugin loading system
    # You do not need this code in your plugins
    get_icons = None
    _ = None

try:
    load_translations()
except NameError:
    pass

try:
    _
except NameError:
    def _(text):
        return text

# The class that all interface action plugins must inherit from
from qt.core import QMenu, QMessageBox, Qt, QToolButton

from calibre.gui2.actions import InterfaceAction
from calibre_plugins.Goodreads_character_and_settings.about import build_about_text
from calibre_plugins.Goodreads_character_and_settings.common import plugin_ui_text, reset_runtime_caches
from calibre_plugins.Goodreads_character_and_settings.database_update import update_database_from_version
from calibre_plugins.Goodreads_character_and_settings.main import GoodreadsPreviewRunner


def ui_text(text):
    return plugin_ui_text(text, _)


def print_supported_language_debug():
    try:
        from calibre.utils.localization import available_translations, get_lang

        active_language = get_lang()
        supported_languages = sorted(set(available_translations()) | {'en'})
        print('Goodreads character and settings supported language debug:', flush=True)
        print('Active language: {}'.format(active_language), flush=True)
        print('Supported language count: {}'.format(len(supported_languages)), flush=True)
        print(
            'Supported languages: {}'.format(', '.join(supported_languages)),
            flush=True,
        )
    except Exception as err:
        print(
            'Goodreads character and settings supported language debug failed: {}'.format(err),
            flush=True,
        )


class InterfacePlugin(InterfaceAction):

    name = ui_text('Goodreads character and settings')
    popup_type = QToolButton.MenuButtonPopup

    action_spec = (ui_text('Goodreads C&&S'), None,
            ui_text('Run Goodreads character and settings'), 'Ctrl+Shift+F1')

    def genesis(self):
        self.current_runner = None
        print_supported_language_debug()
        update_database_from_version()
        icon = get_icons('images/gr_cs_icon.png', ui_text('Goodreads character and settings Plugin'))

        # The qaction is automatically created from the action_spec defined
        # above
        self.qaction.setIcon(icon)
        self.qaction.triggered.connect(self.import_books)
        self.menu = QMenu(self.gui)
        self.qaction.setMenu(self.menu)

        self.import_action = self.menu.addAction(ui_text('Import'))
        self.import_action.triggered.connect(self.import_books)

        self.config_action = self.menu.addAction(ui_text('Customize plugin...'))
        self.config_action.triggered.connect(self.show_config)

        self.about_action = self.menu.addAction(ui_text('About'))
        self.about_action.triggered.connect(self.show_about)

    def import_books(self):
        self.current_runner = GoodreadsPreviewRunner(
            self.gui,
            finished_callback=self.clear_current_runner,
        )
        self.current_runner.run_for_selection()

    def clear_current_runner(self):
        self.current_runner = None

    def show_about(self):
        dialog = QMessageBox(self.gui)
        dialog.setWindowTitle(ui_text('About Goodreads character and settings'))
        dialog.setTextFormat(Qt.TextFormat.RichText)
        dialog.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        dialog.setText(build_about_text())
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        dialog.exec()

    def show_config(self):
        self.interface_action_base_plugin.do_user_config(parent=self.gui)

    def apply_settings(self):
        reset_runtime_caches()
