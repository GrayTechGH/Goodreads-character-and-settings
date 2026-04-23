#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2026, GrayTechGH'
__docformat__ = 'restructuredtext en'

from qt.core import QCheckBox, QComboBox, QFormLayout, QLabel, QSpinBox, QVBoxLayout, QWidget

from calibre.utils.config import JSONConfig

prefs = JSONConfig('plugins/Goodreads_character_and_settings')

FIELD_TAGS = 'tags'
FIELD_NONE = 'none'


prefs.defaults['character_field'] = FIELD_NONE
prefs.defaults['settings_field'] = FIELD_NONE
prefs.defaults['write_empty_to_custom_fields'] = False
prefs.defaults['query_interval_seconds'] = 30


class ConfigWidget(QWidget):

    def __init__(self, custom_fields=None):
        QWidget.__init__(self)

        self.custom_fields = custom_fields or []

        self.l = QVBoxLayout()
        self.setLayout(self.l)

        description = QLabel('Select the character and settings fields')
        description.setWordWrap(True)
        self.l.addWidget(description)

        self.form = QFormLayout()
        self.l.addLayout(self.form)

        self.character_field = self.create_field_combo()
        self.form.addRow('Characters field:', self.character_field)

        self.settings_field = self.create_field_combo()
        self.form.addRow('Settings field:', self.settings_field)

        self.write_empty_to_custom_fields = QCheckBox(
            'Write "Empty" when Goodreads has no value'
        )
        self.write_empty_to_custom_fields.setChecked(
            prefs['write_empty_to_custom_fields']
        )
        self.form.addRow('', self.write_empty_to_custom_fields)

        self.query_interval_seconds = QSpinBox(self)
        self.query_interval_seconds.setMinimum(1)
        self.query_interval_seconds.setMaximum(3600)
        self.query_interval_seconds.setSuffix(' seconds')
        self.query_interval_seconds.setValue(prefs['query_interval_seconds'])
        self.form.addRow('Time between queries:', self.query_interval_seconds)

        self.load_field(self.character_field, prefs['character_field'])
        self.load_field(self.settings_field, prefs['settings_field'])

        self.character_field.currentIndexChanged.connect(
            self.update_empty_option_state
        )
        self.settings_field.currentIndexChanged.connect(
            self.update_empty_option_state
        )
        self.update_empty_option_state()

    def create_field_combo(self):
        combo = QComboBox(self)
        combo.addItem('Do not import', FIELD_NONE)
        combo.addItem('Tags', FIELD_TAGS)
        for lookup_name, display_name in self.custom_fields:
            combo.addItem(display_name, lookup_name)
        return combo

    def load_field(self, combo, value):
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def current_field_uses_custom_column(self, combo):
        value = combo.currentData()
        return value not in (FIELD_NONE, FIELD_TAGS)

    def update_empty_option_state(self):
        enabled = (
            self.current_field_uses_custom_column(self.character_field)
            or self.current_field_uses_custom_column(self.settings_field)
        )
        self.write_empty_to_custom_fields.setEnabled(enabled)
        if enabled:
            self.write_empty_to_custom_fields.setToolTip(
                'If Goodreads does not provide a value, store the text "Empty" '
                'in any selected custom field.'
            )
        else:
            self.write_empty_to_custom_fields.setChecked(False)
            self.write_empty_to_custom_fields.setToolTip(
                'This option is only available when Characters or Settings uses '
                'a custom field.'
            )

    def save_settings(self):
        prefs['character_field'] = self.character_field.currentData()
        prefs['settings_field'] = self.settings_field.currentData()
        prefs['write_empty_to_custom_fields'] = (
            self.write_empty_to_custom_fields.isChecked()
        )
        prefs['query_interval_seconds'] = self.query_interval_seconds.value()
