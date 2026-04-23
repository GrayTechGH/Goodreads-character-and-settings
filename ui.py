#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2026, GrayTechGH'
__docformat__ = 'restructuredtext en'

if False:
    # This is here to keep my python error checker from complaining about
    # the builtin functions that will be defined by the plugin loading system
    # You do not need this code in your plugins
    get_icons = get_resources = None

# The class that all interface action plugins must inherit from
from qt.core import QMenu, QMessageBox, QToolButton

from calibre.gui2.actions import InterfaceAction
from calibre_plugins.Goodreads_character_and_settings.main import GoodreadsPreviewRunner


class InterfacePlugin(InterfaceAction):

    name = 'Goodreads character and settings'
    popup_type = QToolButton.MenuButtonPopup

    action_spec = ('Goodreads C && S', None,
            'Run Goodreads character and settings', 'Ctrl+Shift+F1')

    def genesis(self):
        icon = get_icons('images/gr_cs_icon.png', 'n Goodreads character and settings Plugin')

        # The qaction is automatically created from the action_spec defined
        # above
        self.qaction.setIcon(icon)
        self.qaction.triggered.connect(self.import_books)
        self.menu = QMenu(self.gui)
        self.qaction.setMenu(self.menu)

        self.import_action = self.menu.addAction('Import')
        self.import_action.triggered.connect(self.import_books)

        self.about_action = self.menu.addAction('About')
        self.about_action.triggered.connect(self.show_about)

        self.config_action = self.menu.addAction('Customize plugin...')
        self.config_action.triggered.connect(self.show_config)

    def import_books(self):
        GoodreadsPreviewRunner(self.gui).run_for_selection()

    def show_about(self):
        text = get_resources('about.txt')
        QMessageBox.about(self.gui, 'About Goodreads character and settings',
                text.decode('utf-8'))

    def show_config(self):
        self.interface_action_base_plugin.do_user_config(parent=self.gui)

    def apply_settings(self):
        from calibre_plugins.Goodreads_character_and_settings.config import prefs
        # In an actual non trivial plugin, you would probably need to
        # do something based on the settings in prefs
        prefs
