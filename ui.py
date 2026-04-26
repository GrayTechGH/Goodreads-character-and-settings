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

# The class that all interface action plugins must inherit from
from qt.core import QMenu, QMessageBox, QToolButton

from calibre.gui2.actions import InterfaceAction
from calibre_plugins.Goodreads_character_and_settings.about import build_about_text
from calibre_plugins.Goodreads_character_and_settings.common import reset_runtime_caches
from calibre_plugins.Goodreads_character_and_settings.main import GoodreadsPreviewRunner


class InterfacePlugin(InterfaceAction):

    name = 'Goodreads character and settings'
    popup_type = QToolButton.MenuButtonPopup

    action_spec = ('Goodreads C&&S', None,
            'Run Goodreads character and settings', 'Ctrl+Shift+F1')

    def genesis(self):
        self.current_runner = None
        icon = get_icons('images/gr_cs_icon.png', 'Goodreads character and settings Plugin')

        # The qaction is automatically created from the action_spec defined
        # above
        self.qaction.setIcon(icon)
        self.qaction.triggered.connect(self.import_books)
        self.menu = QMenu(self.gui)
        self.qaction.setMenu(self.menu)

        self.import_action = self.menu.addAction('Import')
        self.import_action.triggered.connect(self.import_books)

        self.config_action = self.menu.addAction('Customize plugin...')
        self.config_action.triggered.connect(self.show_config)

        self.about_action = self.menu.addAction('About')
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
        QMessageBox.about(self.gui, 'About Goodreads character and settings',
                build_about_text())

    def show_config(self):
        self.interface_action_base_plugin.do_user_config(parent=self.gui)

    def apply_settings(self):
        reset_runtime_caches()
