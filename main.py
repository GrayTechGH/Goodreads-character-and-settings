#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

if False:
    get_icons = get_resources = None

from qt.core import QDialog, QLabel, QMessageBox, QPushButton, QVBoxLayout

from calibre_plugins.Goodreads_character_and_settings.config import prefs


class DemoDialog(QDialog):

    def __init__(self, gui, icon, do_user_config):
        QDialog.__init__(self, gui)
        self.gui = gui
        self.do_user_config = do_user_config

        self.l = QVBoxLayout()
        self.setLayout(self.l)

        self.setWindowTitle('Goodreads character and settings')
        self.setWindowIcon(icon)

        self.label = QLabel(self.build_summary())
        self.label.setWordWrap(True)
        self.l.addWidget(self.label)

        self.note = QLabel(
            'Import support is not implemented yet. Use Configure to choose '
            'where character and settings data will go once importing is added.'
        )
        self.note.setWordWrap(True)
        self.l.addWidget(self.note)

        self.about_button = QPushButton('About', self)
        self.about_button.clicked.connect(self.about)
        self.l.addWidget(self.about_button)

        self.conf_button = QPushButton('Configure', self)
        self.conf_button.clicked.connect(self.config)
        self.l.addWidget(self.conf_button)

        self.close_button = QPushButton('Close', self)
        self.close_button.clicked.connect(self.accept)
        self.l.addWidget(self.close_button)

        self.resize(self.sizeHint())

    def build_summary(self):
        character_destination = describe_destination(
            prefs['character_destination'],
            prefs['character_custom_field'],
        )
        settings_destination = describe_destination(
            prefs['settings_destination'],
            prefs['settings_custom_field'],
        )
        empty_behavior = (
            'clear destination fields'
            if prefs['clear_if_missing']
            else 'leave existing values unchanged'
        )

        return (
            'Current configuration:\n'
            f'Characters: {character_destination}\n'
            f'Settings: {settings_destination}\n'
            f'Missing Goodreads values: {empty_behavior}\n'
            f'Time between queries: {prefs["query_interval_seconds"]} seconds'
        )

    def about(self):
        text = get_resources('about.txt')
        QMessageBox.about(
            self,
            'About Goodreads character and settings',
            text.decode('utf-8'),
        )

    def config(self):
        self.do_user_config(parent=self)
        self.label.setText(self.build_summary())


def describe_destination(destination, custom_field_name):
    if destination == 'custom_column':
        field_name = custom_field_name or 'custom field'
        return f'custom field ({field_name})'
    if destination == 'tags':
        return 'tags'
    return 'do not import'
