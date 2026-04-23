from qt.core import QCheckBox, QComboBox, QFormLayout, QLabel, QSpinBox, QVBoxLayout, QWidget

from calibre.utils.config import JSONConfig

PREFS = JSONConfig('plugins/goodreads_character_and_settings')
PREFS.defaults['characters_column'] = ''
PREFS.defaults['settings_column'] = ''
PREFS.defaults['empty_for_custom_fields'] = False
PREFS.defaults['query_delay_seconds'] = 30

TAGS_TARGET = '__tags__'


class ConfigWidget(QWidget):
    def __init__(self, plugin_action):
        super().__init__()
        self.plugin_action = plugin_action
        self.gui = plugin_action.gui

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                'Select the custom columns to populate. Leave either blank to skip that field.'
            )
        )

        form = QFormLayout()
        self.characters_combo = QComboBox(self)
        self.settings_combo = QComboBox(self)
        self.empty_checkbox = QCheckBox('Write "Empty" for missing custom-field values', self)
        self.query_delay_spin = QSpinBox(self)
        self.query_delay_spin.setMinimum(0)
        self.query_delay_spin.setMaximum(300)
        self.query_delay_spin.setSuffix(' s')

        self._populate_combo(self.characters_combo)
        self._populate_combo(self.settings_combo)

        self._select_value(self.characters_combo, PREFS['characters_column'])
        self._select_value(self.settings_combo, PREFS['settings_column'])
        self.empty_checkbox.setChecked(bool(PREFS['empty_for_custom_fields']))
        self.query_delay_spin.setValue(int(PREFS['query_delay_seconds'] or 30))

        form.addRow('Characters destination:', self.characters_combo)
        form.addRow('Settings destination:', self.settings_combo)
        form.addRow('', self.empty_checkbox)
        form.addRow('Seconds between queries:', self.query_delay_spin)
        layout.addLayout(form)
        layout.addStretch(1)

    def _populate_combo(self, combo):
        combo.addItem('(Do not update)', '')
        combo.addItem('Tags', TAGS_TARGET)
        db = self.gui.current_db
        custom = db.field_metadata.custom_field_metadata()
        for key, metadata in sorted(custom.items(), key=lambda item: item[1].get('name', item[0]).lower()):
            datatype = metadata.get('datatype')
            is_multiple = metadata.get('is_multiple')
            if datatype in {'text', 'comments'} or is_multiple:
                name = metadata.get('name', key)
                combo.addItem(f'{name} ({key})', key)

    @staticmethod
    def _select_value(combo, value):
        idx = combo.findData(value)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    def save_settings(self):
        PREFS['characters_column'] = self.characters_combo.currentData() or ''
        PREFS['settings_column'] = self.settings_combo.currentData() or ''
        PREFS['empty_for_custom_fields'] = bool(self.empty_checkbox.isChecked())
        PREFS['query_delay_seconds'] = int(self.query_delay_spin.value())
