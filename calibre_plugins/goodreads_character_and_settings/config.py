from qt.core import QComboBox, QFormLayout, QLabel, QVBoxLayout, QWidget

from calibre.utils.config import JSONConfig

PREFS = JSONConfig('plugins/goodreads_character_and_settings')
PREFS.defaults['characters_column'] = ''
PREFS.defaults['settings_column'] = ''


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

        self._populate_combo(self.characters_combo)
        self._populate_combo(self.settings_combo)

        self._select_value(self.characters_combo, PREFS['characters_column'])
        self._select_value(self.settings_combo, PREFS['settings_column'])

        form.addRow('Characters column:', self.characters_combo)
        form.addRow('Settings column:', self.settings_combo)
        layout.addLayout(form)
        layout.addStretch(1)

    def _populate_combo(self, combo):
        combo.addItem('(Do not update)', '')
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
