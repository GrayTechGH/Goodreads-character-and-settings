#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from qt.core import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from calibre.utils.config import JSONConfig

prefs = JSONConfig('plugins/Goodreads_character_and_settings')

DESTINATION_CUSTOM = 'custom_column'
DESTINATION_TAGS = 'tags'
DESTINATION_NONE = 'none'


prefs.defaults['character_destination'] = DESTINATION_NONE
prefs.defaults['character_custom_field'] = '#characters'
prefs.defaults['settings_destination'] = DESTINATION_NONE
prefs.defaults['settings_custom_field'] = '#settings'
prefs.defaults['clear_if_missing'] = True
prefs.defaults['query_interval_seconds'] = 30


class ConfigWidget(QWidget):

    def __init__(self):
        QWidget.__init__(self)

        self.l = QVBoxLayout()
        self.setLayout(self.l)

        description = QLabel(
            'Choose where Goodreads character and settings data should be stored '
            'when import support is added.'
        )
        description.setWordWrap(True)
        self.l.addWidget(description)

        self.form = QFormLayout()
        self.l.addLayout(self.form)

        self.character_destination = self.create_destination_combo()
        self.character_destination.currentIndexChanged.connect(
            self.update_field_states
        )
        self.form.addRow('Characters destination:', self.character_destination)

        self.character_custom_field = QLineEdit(self)
        self.character_custom_field.setText(prefs['character_custom_field'])
        self.character_custom_field.setPlaceholderText('#characters')
        self.form.addRow(
            'Characters custom field:', self.character_custom_field
        )

        self.settings_destination = self.create_destination_combo()
        self.settings_destination.currentIndexChanged.connect(
            self.update_field_states
        )
        self.form.addRow('Settings destination:', self.settings_destination)

        self.settings_custom_field = QLineEdit(self)
        self.settings_custom_field.setText(prefs['settings_custom_field'])
        self.settings_custom_field.setPlaceholderText('#settings')
        self.form.addRow(
            'Settings custom field:', self.settings_custom_field
        )

        self.clear_if_missing = QCheckBox(
            'Clear the destination field when Goodreads has no value'
        )
        self.clear_if_missing.setChecked(prefs['clear_if_missing'])
        self.form.addRow('', self.clear_if_missing)

        self.query_interval_seconds = QSpinBox(self)
        self.query_interval_seconds.setMinimum(1)
        self.query_interval_seconds.setMaximum(3600)
        self.query_interval_seconds.setSuffix(' seconds')
        self.query_interval_seconds.setValue(prefs['query_interval_seconds'])
        self.form.addRow(
            'Time between queries:', self.query_interval_seconds
        )

        self.load_destination(
            self.character_destination, prefs['character_destination']
        )
        self.load_destination(
            self.settings_destination, prefs['settings_destination']
        )
        self.update_field_states()

    def create_destination_combo(self):
        combo = QComboBox(self)
        combo.addItem('Custom field', DESTINATION_CUSTOM)
        combo.addItem('Tags', DESTINATION_TAGS)
        combo.addItem('Do not import', DESTINATION_NONE)
        return combo

    def load_destination(self, combo, value):
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def update_field_states(self):
        character_is_custom = (
            self.character_destination.currentData() == DESTINATION_CUSTOM
        )
        settings_is_custom = (
            self.settings_destination.currentData() == DESTINATION_CUSTOM
        )
        self.character_custom_field.setEnabled(character_is_custom)
        self.settings_custom_field.setEnabled(settings_is_custom)

    def validate(self):
        if (
            self.character_destination.currentData() == DESTINATION_CUSTOM
            and not self.character_custom_field.text().strip()
        ):
            QMessageBox.warning(
                self,
                'Missing custom field',
                'Enter a custom field lookup name for Characters or choose Tags '
                'or Do not import.',
            )
            return False

        if (
            self.settings_destination.currentData() == DESTINATION_CUSTOM
            and not self.settings_custom_field.text().strip()
        ):
            QMessageBox.warning(
                self,
                'Missing custom field',
                'Enter a custom field lookup name for Settings or choose Tags '
                'or Do not import.',
            )
            return False

        return True

    def save_settings(self):
        prefs['character_destination'] = self.character_destination.currentData()
        prefs['character_custom_field'] = (
            self.character_custom_field.text().strip()
        )
        prefs['settings_destination'] = self.settings_destination.currentData()
        prefs['settings_custom_field'] = (
            self.settings_custom_field.text().strip()
        )
        prefs['clear_if_missing'] = self.clear_if_missing.isChecked()
        prefs['query_interval_seconds'] = self.query_interval_seconds.value()
