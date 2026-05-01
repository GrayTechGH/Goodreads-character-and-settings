#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2026, GrayTechGH'
__docformat__ = 'restructuredtext en'

try:
    load_translations()
except NameError:
    pass

try:
    _
except NameError:
    def _(text):
        return text

import re

from qt.core import (
    QAbstractItemView,
    QAbstractScrollArea,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSize,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    Qt,
)

from calibre.utils.config import JSONConfig
from calibre_plugins.Goodreads_character_and_settings.settings_data import (
    AUTODELETE_MODE_LITERAL,
    AUTODELETE_MODE_REGEX,
    AUTODELETE_MODE_WILDCARD,
    AUTODELETE_SCOPE_BOTH,
    AUTODELETE_SCOPE_CHARACTERS,
    AUTODELETE_SCOPE_SETTINGS,
    COUNTRY_NAME_LANGUAGE_AUTO,
    COUNTRY_NAME_LANGUAGE_ENGLISH_FORMAL,
    COUNTRY_NAME_LANGUAGE_ENGLISH_SHORT,
    COUNTRY_NAME_MODE_ALIAS,
    COUNTRY_NAME_MODE_COUNTRY,
    build_default_user_data,
    consume_user_json_repair_flag,
    country_name_language_display_name,
    country_name_language_options,
    ensure_user_json_files,
    load_user_autodelete_values,
    load_user_country_data,
    load_user_region_data,
    normalize_country_code,
    save_user_autodelete_values,
    save_user_country_data,
    save_user_region_data,
)


prefs = JSONConfig('plugins/Goodreads_character_and_settings')

FIELD_TAGS = 'tags'
FIELD_NONE = 'none'
CONFIG_DIALOG_DEFAULT_SIZE = QSize(900, 640)
CONFIG_DIALOG_MINIMUM_SIZE = QSize(640, 460)
AUTODELETE_RULE_DIALOG_DEFAULT_SIZE = QSize(560, 220)
AUTODELETE_RULE_DIALOG_MINIMUM_SIZE = QSize(440, 180)
AUTODELETE_COLUMN_DEFAULT_WIDTHS = [70, 0, 90, 100, 120]
AUTODELETE_MODES = (
    (AUTODELETE_MODE_LITERAL, _('Literal')),
    (AUTODELETE_MODE_WILDCARD, _('Wildcard')),
    (AUTODELETE_MODE_REGEX, _('Regex')),
)
AUTODELETE_SCOPES = (
    (AUTODELETE_SCOPE_SETTINGS, _('Settings')),
    (AUTODELETE_SCOPE_CHARACTERS, _('Characters')),
    (AUTODELETE_SCOPE_BOTH, _('Both')),
)


prefs.defaults['character_field'] = FIELD_NONE
prefs.defaults['settings_field'] = FIELD_NONE
prefs.defaults['countries_field'] = FIELD_NONE
prefs.defaults['include_country_with_location'] = True
prefs.defaults['keep_region_in_settings'] = True
prefs.defaults['write_empty_to_custom_fields'] = False
prefs.defaults['query_interval_seconds'] = 30
prefs.defaults['max_books_per_job'] = 5
prefs.defaults['debug_preview'] = False
prefs.defaults['debug_character_sources'] = False
prefs.defaults['debug_settings_pipeline'] = False
prefs.defaults['country_name_language'] = COUNTRY_NAME_LANGUAGE_AUTO
prefs.defaults['country_name_mode'] = COUNTRY_NAME_MODE_ALIAS
prefs.defaults['autodelete_column_widths'] = AUTODELETE_COLUMN_DEFAULT_WIDTHS


class ConfigWidget(QWidget):
    validate_before_accept = True

    def __init__(self, custom_fields=None):
        QWidget.__init__(self)
        self.setMinimumSize(CONFIG_DIALOG_MINIMUM_SIZE)
        self.resize(CONFIG_DIALOG_DEFAULT_SIZE)

        self.custom_fields = custom_fields or []
        ensure_user_json_files()
        self._loading_tables = False
        self._countries_dirty = False
        self._regions_dirty = False
        self._autodelete_dirty = False

        self.l = QVBoxLayout()
        self.setLayout(self.l)

        self.tabs = QTabWidget(self)
        self.l.addWidget(self.tabs)

        self.main_tab = QWidget(self)
        self.countries_tab = QWidget(self)
        self.regions_tab = QWidget(self)
        self.autodelete_tab = QWidget(self)

        self.tabs.addTab(self.main_tab, _('Main'))
        self.tabs.addTab(self.countries_tab, _('Countries'))
        self.tabs.addTab(self.regions_tab, _('Regions'))
        self.tabs.addTab(self.autodelete_tab, _('Autodelete'))
        self.tabs.currentChanged.connect(self.update_restore_defaults_button)

        self.build_main_tab()
        self.build_countries_tab()
        self.build_regions_tab()
        self.build_autodelete_tab()
        self.build_footer()

        self.load_main_settings()
        country_data = load_user_country_data()
        self._countries_dirty = consume_user_json_repair_flag('countries')
        self.load_country_rows(country_data)

        region_data = load_user_region_data()
        self._regions_dirty = consume_user_json_repair_flag('regions')
        if self.load_region_rows(region_data):
            self._regions_dirty = True

        autodelete_data = load_user_autodelete_values()
        self._autodelete_dirty = consume_user_json_repair_flag('autodelete')
        self.load_autodelete_rows(autodelete_data)
        self.update_empty_option_state()
        self.update_restore_defaults_button()

    def sizeHint(self):
        return CONFIG_DIALOG_DEFAULT_SIZE

    def build_main_tab(self):
        layout = QVBoxLayout()
        self.main_tab.setLayout(layout)

        description = QLabel(_('Select the character and settings fields'))
        description.setWordWrap(True)
        layout.addWidget(description)

        self.form = QFormLayout()
        layout.addLayout(self.form)

        self.character_field = self.create_field_combo()
        self.form.addRow(_('Characters field:'), self.character_field)

        self.settings_field = self.create_field_combo()
        self.form.addRow(_('Settings field:'), self.settings_field)

        self.countries_field = self.create_field_combo()
        self.form.addRow(_('Countries field:'), self.countries_field)

        self.country_name_language = QComboBox(self)
        self.country_name_language.addItem(_('Active calibre language'), COUNTRY_NAME_LANGUAGE_AUTO)
        self.country_name_language.addItem(
            _('English short names'),
            COUNTRY_NAME_LANGUAGE_ENGLISH_SHORT,
        )
        self.country_name_language.addItem(
            _('English formal names'),
            COUNTRY_NAME_LANGUAGE_ENGLISH_FORMAL,
        )
        for language in country_name_language_options():
            if language == 'en':
                continue
            self.country_name_language.addItem(
                country_name_language_display_name(language),
                language,
            )
        self.form.addRow(_('Country names language:'), self.country_name_language)

        self.localize_country_names = QCheckBox(_('Localize country names'))
        self.localize_country_names.setToolTip(
            _('Use the selected-language country names as country values. '
                    'The selected-language names are also kept as aliases.')
        )
        self.form.addRow('', self.localize_country_names)

        self.include_country_with_location = QCheckBox(
            _('Keep country in settings field')
        )
        self.include_country_with_location.setChecked(
            prefs['include_country_with_location']
        )
        self.include_country_with_location.setToolTip(
            _('Keep the country in parentheses in the Settings field while also writing it to the Countries field.')
        )
        self.form.addRow('', self.include_country_with_location)

        self.keep_region_in_settings = QCheckBox(
            _('Keep region in settings field')
        )
        self.keep_region_in_settings.setChecked(
            prefs['keep_region_in_settings']
        )
        self.keep_region_in_settings.setToolTip(
            _('Keep region or subdivision values such as states, provinces, and countries-in-Regions mappings in the Settings field.')
        )
        self.form.addRow('', self.keep_region_in_settings)

        self.write_empty_to_custom_fields = QCheckBox(
            _('Write "Empty" when Goodreads has no value')
        )
        self.write_empty_to_custom_fields.setChecked(
            prefs['write_empty_to_custom_fields']
        )
        self.form.addRow('', self.write_empty_to_custom_fields)

        self.query_interval_seconds = QSpinBox(self)
        self.query_interval_seconds.setMinimum(1)
        self.query_interval_seconds.setMaximum(3600)
        self.query_interval_seconds.setSuffix(_(' seconds'))
        self.query_interval_seconds.setValue(prefs['query_interval_seconds'])
        self.form.addRow(_('Time between queries:'), self.query_interval_seconds)

        self.max_books_per_job = QSpinBox(self)
        self.max_books_per_job.setMinimum(1)
        self.max_books_per_job.setMaximum(100000)
        self.max_books_per_job.setValue(prefs['max_books_per_job'])
        self.form.addRow(_('Max. Books/Job:'), self.max_books_per_job)

        self.character_field.currentIndexChanged.connect(
            self.update_empty_option_state
        )
        self.settings_field.currentIndexChanged.connect(
            self.update_empty_option_state
        )
        self.countries_field.currentIndexChanged.connect(
            self.update_empty_option_state
        )
        self.country_name_language.currentIndexChanged.connect(
            self.country_name_language_changed
        )
        self.localize_country_names.stateChanged.connect(
            self.country_name_options_changed
        )

        layout.addStretch(1)

    def build_countries_tab(self):
        layout = QVBoxLayout()
        self.countries_tab.setLayout(layout)

        description = QLabel(
            _('Countries table. Add one canonical country per row, optional ISO '
                    'country code, and any aliases as a comma-separated list.')
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        self.countries_table = QTableWidget(0, 3, self)
        self.countries_table.setHorizontalHeaderLabels([_('Country'), _('ISO'), _('Aliases')])
        self.countries_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.countries_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.countries_table.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)
        self.countries_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.countries_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.countries_table.verticalHeader().setVisible(False)
        self.countries_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.countries_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.countries_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.countries_table.itemChanged.connect(self.country_table_item_changed)
        layout.addWidget(self.countries_table)

        buttons = QHBoxLayout()
        self.add_country_button = QPushButton(_('Add'), self)
        self.remove_country_button = QPushButton(_('Remove'), self)
        self.add_country_button.clicked.connect(self.add_country_row)
        self.remove_country_button.clicked.connect(self.remove_country_row)
        buttons.addWidget(self.add_country_button)
        buttons.addWidget(self.remove_country_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

    def build_regions_tab(self):
        layout = QVBoxLayout()
        self.regions_tab.setLayout(layout)

        description = QLabel(
            _('Regions table. Each region is preserved in Settings and mapped to '
                    'the selected country in Countries.')
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        self.regions_table = QTableWidget(0, 2, self)
        self.regions_table.setHorizontalHeaderLabels([_('Country'), _('Regions')])
        self.regions_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.regions_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.regions_table.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)
        self.regions_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.regions_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.regions_table.verticalHeader().setVisible(False)
        self.regions_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.regions_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.regions_table.itemChanged.connect(self.regions_table_item_changed)
        layout.addWidget(self.regions_table)

        buttons = QHBoxLayout()
        self.add_region_button = QPushButton(_('Add'), self)
        self.remove_region_button = QPushButton(_('Remove'), self)
        self.add_region_button.clicked.connect(self.add_region_row)
        self.remove_region_button.clicked.connect(self.remove_region_row)
        buttons.addWidget(self.add_region_button)
        buttons.addWidget(self.remove_region_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

    def build_autodelete_tab(self):
        layout = QVBoxLayout()
        self.autodelete_tab.setLayout(layout)

        description = QLabel(
            _('Values listed here are automatically removed if Goodreads returns '
                    'matching Characters or Settings values.')
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        self.autodelete_table = QTableWidget(0, 5, self)
        self.autodelete_table.setHorizontalHeaderLabels([
            _('Enabled'),
            _('Match'),
            _('Mode'),
            _('Columns'),
            _('Case'),
        ])
        self.autodelete_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.autodelete_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.autodelete_table.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)
        self.autodelete_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.autodelete_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.autodelete_table.verticalHeader().setVisible(False)
        self.autodelete_table.setColumnWidth(0, 70)
        self.autodelete_table.setColumnWidth(2, 90)
        self.autodelete_table.setColumnWidth(3, 100)
        self.autodelete_table.setColumnWidth(4, 120)
        self.autodelete_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.autodelete_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.autodelete_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.autodelete_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.autodelete_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        self.restore_autodelete_column_widths()
        self.autodelete_table.itemChanged.connect(self.autodelete_table_item_changed)
        self.autodelete_table.doubleClicked.connect(self.edit_autodelete_row)
        layout.addWidget(self.autodelete_table)

        buttons = QHBoxLayout()
        self.add_autodelete_button = QPushButton(_('Add'), self)
        self.edit_autodelete_button = QPushButton(_('Edit'), self)
        self.remove_autodelete_button = QPushButton(_('Remove'), self)
        self.add_autodelete_button.clicked.connect(self.add_autodelete_row)
        self.edit_autodelete_button.clicked.connect(self.edit_autodelete_row)
        self.remove_autodelete_button.clicked.connect(self.remove_autodelete_row)
        buttons.addWidget(self.add_autodelete_button)
        buttons.addWidget(self.edit_autodelete_button)
        buttons.addWidget(self.remove_autodelete_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

    def build_footer(self):
        footer = QHBoxLayout()
        self.restore_defaults_button = QPushButton(_('Restore defaults'), self)
        self.restore_defaults_button.clicked.connect(self.restore_user_json_defaults)
        footer.addWidget(self.restore_defaults_button)
        footer.addStretch(1)
        self.l.addLayout(footer)

    def update_restore_defaults_button(self, *_args):
        self.restore_defaults_button.setVisible(
            self.tabs.currentWidget() is not self.autodelete_tab
        )

    def create_field_combo(self):
        combo = QComboBox(self)
        combo.addItem(_('Do not import'), FIELD_NONE)
        combo.addItem(_('Tags'), FIELD_TAGS)
        for lookup_name, display_name in self.custom_fields:
            combo.addItem(display_name, lookup_name)
        return combo

    def load_field(self, combo, value):
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def load_main_settings(self):
        self.load_field(self.character_field, prefs['character_field'])
        self.load_field(self.settings_field, prefs['settings_field'])
        self.load_field(self.countries_field, prefs['countries_field'])
        self.load_field(self.country_name_language, prefs['country_name_language'])
        self.localize_country_names.setChecked(
            prefs['country_name_mode'] == COUNTRY_NAME_MODE_COUNTRY
        )

    def current_field_uses_custom_column(self, combo):
        value = combo.currentData()
        return value not in (FIELD_NONE, FIELD_TAGS)

    def update_empty_option_state(self):
        enabled = (
            self.current_field_uses_custom_column(self.character_field)
            or self.current_field_uses_custom_column(self.settings_field)
            or self.current_field_uses_custom_column(self.countries_field)
        )
        self.write_empty_to_custom_fields.setEnabled(enabled)
        if enabled:
            self.write_empty_to_custom_fields.setToolTip(
                _('If Goodreads does not provide a value, store the text "Empty" '
                        'in any selected custom field.')
            )
        else:
            self.write_empty_to_custom_fields.setChecked(False)
            self.write_empty_to_custom_fields.setToolTip(
                _('This option is only available when Characters, Settings, or '
                        'Countries uses a custom field.')
            )

    def country_table_item_changed(self, _item):
        if not self._loading_tables:
            self._countries_dirty = True
        self.refresh_region_country_combos()

    def country_name_options_changed(self, *_args):
        if self._loading_tables:
            return
        self.apply_selected_country_names_to_table()

    def country_name_language_changed(self, *_args):
        if self._loading_tables:
            return
        if self.localize_country_names.isChecked():
            self.localize_country_names.setChecked(False)
            return
        self.apply_selected_country_names_to_table()

    def apply_selected_country_names_to_table(self):
        defaults = build_default_user_data(
            country_name_language=self.country_name_language.currentData(),
            country_name_mode=self.current_country_name_mode(),
        )
        default_names_by_iso = {
            normalize_country_code(item.get('iso', '')): item.get('country', '')
            for item in defaults.get('countries', []) or []
            if normalize_country_code(item.get('iso', ''))
        }
        if not default_names_by_iso:
            return

        self._loading_tables = True
        self.countries_table.blockSignals(True)
        changed = False
        for row in range(self.countries_table.rowCount()):
            country_item = self.countries_table.item(row, 0)
            iso_item = self.countries_table.item(row, 1)
            iso = normalize_country_code(iso_item.text() if iso_item else '')
            country = default_names_by_iso.get(iso)
            if not country:
                continue
            current_country = str(country_item.text() if country_item else '').strip()
            if current_country == country:
                continue
            self.add_country_alias(row, current_country)
            self.set_table_text(self.countries_table, row, 0, country)
            self.add_country_alias(row, country)
            changed = True
        self.countries_table.blockSignals(False)
        self._loading_tables = False

        if changed:
            self._countries_dirty = True
            self._regions_dirty = True
            self.sync_region_country_names()
            self.refresh_region_country_combos()

    def sync_region_country_names(self):
        country_names_by_key = {
            item['key']: item['country']
            for item in self.current_country_records()
        }
        for row in range(self.regions_table.rowCount()):
            combo = self.regions_table.cellWidget(row, 0)
            if combo is None:
                continue
            country_key = str(combo.currentData() or '')
            country = country_names_by_key.get(country_key)
            if country:
                self.regions_table.setCellWidget(
                    row,
                    0,
                    self.create_region_country_combo(country_key, country),
                )

    def regions_table_item_changed(self, _item):
        if not self._loading_tables:
            self._regions_dirty = True

    def autodelete_table_item_changed(self, _item):
        if not self._loading_tables:
            self._autodelete_dirty = True

    def selected_table_rows(self, table):
        return sorted(
            {index.row() for index in table.selectionModel().selectedRows()},
            reverse=True,
        )

    def country_keys_for_rows(self, rows):
        keys = set()
        for row in rows:
            country_item = self.countries_table.item(row, 0)
            iso_item = self.countries_table.item(row, 1)
            country = str(country_item.text() if country_item else '').strip()
            iso = normalize_country_code(iso_item.text() if iso_item else '')
            key = self.country_record_key(country, iso)
            if key:
                keys.add(key)
        return keys

    def region_rows_for_country_keys(self, country_keys):
        rows = []
        for row in range(self.regions_table.rowCount()):
            combo = self.regions_table.cellWidget(row, 0)
            country_key = str(combo.currentData() if combo is not None else '')
            if country_key in country_keys:
                rows.append(row)
        return sorted(rows, reverse=True)

    def confirm_remove_country_region_mappings(self, country_count, region_count):
        if region_count <= 0:
            return True
        if country_count == 1:
            message = _(
                'Removing this country will also remove its region mappings. Continue?'
            )
        else:
            message = _(
                'Removing these countries will also remove their region mappings. Continue?'
            )
        result = QMessageBox.question(
            self,
            _('Countries'),
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    def restore_autodelete_column_widths(self):
        widths = prefs.get('autodelete_column_widths', AUTODELETE_COLUMN_DEFAULT_WIDTHS)
        if not isinstance(widths, list):
            widths = AUTODELETE_COLUMN_DEFAULT_WIDTHS
        for column, width in enumerate(widths[:self.autodelete_table.columnCount()]):
            if column == 1:
                continue
            try:
                width = int(width)
            except Exception:
                continue
            if width > 0:
                self.autodelete_table.setColumnWidth(column, width)

    def current_autodelete_column_widths(self):
        widths = []
        for column in range(self.autodelete_table.columnCount()):
            if column == 1:
                widths.append(0)
            else:
                widths.append(self.autodelete_table.columnWidth(column))
        return widths

    def current_country_names(self):
        names = []
        seen = set()
        for item in self.current_country_records():
            lowered = item['country'].lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            names.append(item['country'])
        names.sort(key=lambda item: item.lower())
        return names

    def current_country_records(self):
        records = []
        seen = set()
        for row in range(self.countries_table.rowCount()):
            country_item = self.countries_table.item(row, 0)
            iso_item = self.countries_table.item(row, 1)
            country = str(country_item.text() if country_item else '').strip()
            iso = normalize_country_code(iso_item.text() if iso_item else '')
            if not country:
                continue
            key = self.country_record_key(country, iso)
            if key in seen:
                continue
            seen.add(key)
            records.append({
                'country': country,
                'iso': iso,
                'key': key,
            })
        records.sort(key=lambda item: item['country'].lower())
        return records

    def country_record_key(self, country, iso=''):
        iso = normalize_country_code(iso)
        if iso:
            return iso
        return str(country or '').strip().casefold()

    def create_region_country_combo(self, selected_key='', selected_country=''):
        combo = QComboBox(self.regions_table)
        countries = self.current_country_records()
        if not countries:
            combo.addItem('', '')
        else:
            for country in countries:
                combo.addItem(country['country'], country['key'])
        if selected_key:
            index = combo.findData(selected_key)
            if index < 0:
                combo.addItem(selected_country or selected_key, selected_key)
                index = combo.findData(selected_key)
            combo.setCurrentIndex(index)
        combo.currentIndexChanged.connect(self.region_country_combo_changed)
        return combo

    def region_country_combo_changed(self, _index):
        if not self._loading_tables:
            self._regions_dirty = True

    def prompt_for_existing_country(self, title, label):
        countries = self.current_country_records()
        if not countries:
            QMessageBox.warning(self, title, _('Add a country first.'))
            return ''
        labels = [
            '{} ({})'.format(item['country'], item['iso']) if item['iso'] else item['country']
            for item in countries
        ]
        country_label, accepted = QInputDialog.getItem(
            self,
            title,
            label,
            labels,
            0,
            False,
        )
        if not accepted:
            return ''
        selected_index = labels.index(country_label)
        return countries[selected_index]['key']

    def prompt_for_unique_country(self, title, label, existing_names=None):
        existing = {name.lower() for name in (existing_names or [])}
        while True:
            value, accepted = QInputDialog.getText(self, title, label)
            if not accepted:
                return ''
            country = str(value).strip()
            if not country:
                QMessageBox.warning(self, title, _('Country name cannot be empty.'))
                continue
            if country.lower() in existing:
                QMessageBox.warning(self, title, _('Country name must be unique.'))
                continue
            return country

    def refresh_region_country_combos(self):
        for row in range(self.regions_table.rowCount()):
            combo = self.regions_table.cellWidget(row, 0)
            if combo is None:
                continue
            current_value = combo.currentData() or combo.currentText()
            new_combo = self.create_region_country_combo(current_value, combo.currentText())
            self.regions_table.setCellWidget(row, 0, new_combo)

    def set_table_text(self, table, row, column, value):
        item = QTableWidgetItem(value)
        table.setItem(row, column, item)

    def add_country_alias(self, row, value):
        value = str(value or '').strip()
        if not value:
            return
        aliases_item = self.countries_table.item(row, 2)
        aliases = [
            part.strip()
            for part in str(aliases_item.text() if aliases_item else '').split(',')
            if part.strip()
        ]
        seen = {alias.casefold() for alias in aliases}
        if value.casefold() in seen:
            return
        aliases.append(value)
        self.set_table_text(self.countries_table, row, 2, ', '.join(aliases))

    def add_country_row(self, country='', iso='', aliases='', refresh_region_combos=True, activate_row=True):
        if not country:
            country = self.prompt_for_unique_country(
                _('Add Country'),
                _('Country name:'),
                self.current_country_names(),
            )
            if not country:
                return
        iso = normalize_country_code(iso)
        row = self.countries_table.rowCount()
        self.countries_table.insertRow(row)
        self.set_table_text(self.countries_table, row, 0, country)
        self.set_table_text(self.countries_table, row, 1, iso)
        self.set_table_text(self.countries_table, row, 2, aliases)
        if activate_row:
            self.countries_table.setCurrentCell(row, 0)
            self.countries_table.selectRow(row)
            self.countries_table.scrollToItem(self.countries_table.item(row, 0))
        if refresh_region_combos:
            self.refresh_region_country_combos()
        if not self._loading_tables:
            self._countries_dirty = True

    def remove_country_row(self):
        rows = self.selected_table_rows(self.countries_table)
        if not rows and self.countries_table.currentRow() >= 0:
            rows = [self.countries_table.currentRow()]
        if rows:
            country_keys = self.country_keys_for_rows(rows)
            region_rows = self.region_rows_for_country_keys(country_keys)
            if not self.confirm_remove_country_region_mappings(len(rows), len(region_rows)):
                return
            for row in region_rows:
                self.regions_table.removeRow(row)
            for row in rows:
                self.countries_table.removeRow(row)
            self.refresh_region_country_combos()
            if not self._loading_tables:
                self._countries_dirty = True
                if region_rows:
                    self._regions_dirty = True

    def add_region_row(self, country_key='', country='', region='', iso=''):
        country_key = str(country_key or '')
        iso = normalize_country_code(iso)
        if not country_key:
            country_key = self.prompt_for_existing_country(
                _('Add Regions Country'),
                _('Country name:'),
            )
            if not country_key:
                return
        if not country:
            for item in self.current_country_records():
                if item['key'] == country_key:
                    country = item['country']
                    iso = item['iso']
                    break
        elif not iso:
            for item in self.current_country_records():
                if item['key'] == country_key:
                    iso = item['iso']
                    break
        row = self.regions_table.rowCount()
        self.regions_table.insertRow(row)
        self.regions_table.setCellWidget(row, 0, self.create_region_country_combo(country_key, country))
        self.set_table_text(self.regions_table, row, 1, region)
        if not self._loading_tables:
            self._regions_dirty = True

    def remove_region_row(self):
        rows = self.selected_table_rows(self.regions_table)
        if not rows and self.regions_table.currentRow() >= 0:
            rows = [self.regions_table.currentRow()]
        if rows:
            for row in rows:
                self.regions_table.removeRow(row)
            if not self._loading_tables:
                self._regions_dirty = True

    def autodelete_mode_label(self, mode):
        for value, label in AUTODELETE_MODES:
            if value == mode:
                return label
        return _('Literal')

    def autodelete_scope_label(self, scope):
        for value, label in AUTODELETE_SCOPES:
            if value == scope:
                return label
        return _('Both')

    def set_checkable_table_item(self, table, row, column, checked):
        item = QTableWidgetItem('')
        item.setFlags(
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsUserCheckable
        )
        item.setCheckState(
            Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        )
        table.setItem(row, column, item)

    def set_readonly_table_text(self, table, row, column, value):
        item = QTableWidgetItem(str(value or ''))
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        table.setItem(row, column, item)

    def autodelete_rule_from_dialog(self, existing=None):
        existing = existing or {}
        dialog = QDialog(self)
        dialog.setMinimumSize(AUTODELETE_RULE_DIALOG_MINIMUM_SIZE)
        dialog.resize(AUTODELETE_RULE_DIALOG_DEFAULT_SIZE)
        dialog.setWindowTitle(
            _('Edit auto-delete rule') if existing.get('pattern') else _('Add auto-delete rule')
        )
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.addLayout(form)

        pattern = QLineEdit(dialog)
        pattern.setText(existing.get('pattern', ''))
        form.addRow(_('Match:'), pattern)

        mode = QComboBox(dialog)
        for value, label in AUTODELETE_MODES:
            mode.addItem(label, value)
        mode.setMaximumWidth(180)
        mode_index = mode.findData(existing.get('mode', AUTODELETE_MODE_LITERAL))
        mode.setCurrentIndex(mode_index if mode_index >= 0 else 0)
        form.addRow(_('Match mode:'), mode)

        scope = QComboBox(dialog)
        for value, label in AUTODELETE_SCOPES:
            scope.addItem(label, value)
        scope.setMaximumWidth(180)
        scope_index = scope.findData(existing.get('scope', AUTODELETE_SCOPE_SETTINGS))
        scope.setCurrentIndex(scope_index if scope_index >= 0 else 0)
        form.addRow(_('Columns:'), scope)

        case_sensitive = QCheckBox(_('Case sensitive'), dialog)
        case_sensitive.setChecked(bool(existing.get('case_sensitive', False)))
        form.addRow('', case_sensitive)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            dialog,
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        while dialog.exec() == QDialog.DialogCode.Accepted:
            value = str(pattern.text() or '').strip()
            if not value:
                QMessageBox.warning(dialog, dialog.windowTitle(), _('Match cannot be empty.'))
                continue
            if mode.currentData() == AUTODELETE_MODE_REGEX:
                try:
                    re.compile(value)
                except re.error as err:
                    QMessageBox.warning(
                        dialog,
                        dialog.windowTitle(),
                        _('Invalid regular expression: {}').format(err),
                    )
                    continue
            return {
                'enabled': bool(existing.get('enabled', True)),
                'pattern': value,
                'mode': mode.currentData(),
                'scope': scope.currentData(),
                'case_sensitive': case_sensitive.isChecked(),
            }
        return None

    def autodelete_rule_for_row(self, row):
        enabled_item = self.autodelete_table.item(row, 0)
        pattern_item = self.autodelete_table.item(row, 1)
        mode_item = self.autodelete_table.item(row, 2)
        scope_item = self.autodelete_table.item(row, 3)
        case_item = self.autodelete_table.item(row, 4)
        pattern = str(pattern_item.text() if pattern_item else '').strip()
        if not pattern:
            return None
        return {
            'enabled': (
                enabled_item is None
                or enabled_item.checkState() == Qt.CheckState.Checked
            ),
            'pattern': pattern,
            'mode': mode_item.data(Qt.ItemDataRole.UserRole) if mode_item else AUTODELETE_MODE_LITERAL,
            'scope': scope_item.data(Qt.ItemDataRole.UserRole) if scope_item else AUTODELETE_SCOPE_BOTH,
            'case_sensitive': (
                case_item is not None
                and case_item.checkState() == Qt.CheckState.Checked
            ),
        }

    def add_autodelete_row(self, rule=None):
        if not isinstance(rule, dict):
            starting_rule = {
                'enabled': True,
                'pattern': rule if isinstance(rule, str) else '',
                'mode': AUTODELETE_MODE_LITERAL,
                'scope': AUTODELETE_SCOPE_SETTINGS,
                'case_sensitive': False,
            }
            rule = self.autodelete_rule_from_dialog(starting_rule)
            if not rule:
                return
        row = self.autodelete_table.rowCount()
        self.autodelete_table.insertRow(row)
        self.set_checkable_table_item(
            self.autodelete_table,
            row,
            0,
            bool(rule.get('enabled', True)),
        )
        self.set_readonly_table_text(self.autodelete_table, row, 1, rule.get('pattern', ''))
        mode_item = QTableWidgetItem(self.autodelete_mode_label(rule.get('mode')))
        mode_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        mode_item.setData(Qt.ItemDataRole.UserRole, rule.get('mode', AUTODELETE_MODE_LITERAL))
        self.autodelete_table.setItem(row, 2, mode_item)
        scope_item = QTableWidgetItem(self.autodelete_scope_label(rule.get('scope')))
        scope_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        scope_item.setData(Qt.ItemDataRole.UserRole, rule.get('scope', AUTODELETE_SCOPE_BOTH))
        self.autodelete_table.setItem(row, 3, scope_item)
        self.set_checkable_table_item(
            self.autodelete_table,
            row,
            4,
            bool(rule.get('case_sensitive', False)),
        )
        self.autodelete_table.setCurrentCell(row, 1)
        self.autodelete_table.selectRow(row)
        if not self._loading_tables:
            self._autodelete_dirty = True

    def edit_autodelete_row(self, *_args):
        row = self.autodelete_table.currentRow()
        if row < 0:
            return
        existing = self.autodelete_rule_for_row(row)
        if not existing:
            return
        updated = self.autodelete_rule_from_dialog(existing)
        if not updated:
            return
        self.autodelete_table.blockSignals(True)
        enabled_item = self.autodelete_table.item(row, 0)
        if enabled_item is not None:
            enabled_item.setCheckState(
                Qt.CheckState.Checked if updated.get('enabled', True) else Qt.CheckState.Unchecked
            )
        self.set_readonly_table_text(self.autodelete_table, row, 1, updated.get('pattern', ''))
        mode_item = QTableWidgetItem(self.autodelete_mode_label(updated.get('mode')))
        mode_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        mode_item.setData(Qt.ItemDataRole.UserRole, updated.get('mode', AUTODELETE_MODE_LITERAL))
        self.autodelete_table.setItem(row, 2, mode_item)
        scope_item = QTableWidgetItem(self.autodelete_scope_label(updated.get('scope')))
        scope_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        scope_item.setData(Qt.ItemDataRole.UserRole, updated.get('scope', AUTODELETE_SCOPE_BOTH))
        self.autodelete_table.setItem(row, 3, scope_item)
        case_item = self.autodelete_table.item(row, 4)
        if case_item is not None:
            case_item.setCheckState(
                Qt.CheckState.Checked if updated.get('case_sensitive', False) else Qt.CheckState.Unchecked
            )
        self.autodelete_table.blockSignals(False)
        if not self._loading_tables:
            self._autodelete_dirty = True

    def remove_autodelete_row(self):
        rows = self.selected_table_rows(self.autodelete_table)
        if not rows and self.autodelete_table.currentRow() >= 0:
            rows = [self.autodelete_table.currentRow()]
        if rows:
            for row in rows:
                self.autodelete_table.removeRow(row)
            if not self._loading_tables:
                self._autodelete_dirty = True

    def load_country_rows(self, countries):
        self._loading_tables = True
        self.countries_table.blockSignals(True)
        self.countries_table.setUpdatesEnabled(False)
        self.countries_table.setRowCount(0)
        for item in countries:
            self.add_country_row(
                item.get('country', ''),
                item.get('iso', ''),
                ', '.join(item.get('aliases', []) or []),
                refresh_region_combos=False,
                activate_row=False,
            )
        self.countries_table.blockSignals(False)
        self.countries_table.setUpdatesEnabled(True)
        self._loading_tables = False
        self.refresh_region_country_combos()

    def load_region_rows(self, regions):
        self._loading_tables = True
        self.regions_table.blockSignals(True)
        self.regions_table.setUpdatesEnabled(False)
        self.regions_table.setRowCount(0)
        valid_country_keys = {
            item['key']
            for item in self.current_country_records()
        }
        skipped_orphan_regions = False
        grouped = {}
        for item in regions:
            iso = normalize_country_code(item.get('iso', ''))
            country = item.get('country', '')
            region = item.get('region', '')
            if not country or not region:
                continue
            country_key = self.country_record_key(country, iso)
            if country_key not in valid_country_keys:
                skipped_orphan_regions = True
                continue
            grouped.setdefault(country_key, {
                'country': country,
                'iso': iso,
                'regions': [],
            })['regions'].append(region)
        for country_key, group in sorted(grouped.items(), key=lambda item: item[1]['country'].lower()):
            unique_regions = []
            seen = set()
            for region in group['regions']:
                lowered = region.lower()
                if lowered in seen:
                    continue
                seen.add(lowered)
                unique_regions.append(region)
            self.add_region_row(country_key, group['country'], ', '.join(unique_regions), group['iso'])
        self.regions_table.blockSignals(False)
        self.regions_table.setUpdatesEnabled(True)
        self._loading_tables = False
        return skipped_orphan_regions

    def load_autodelete_rows(self, values):
        self._loading_tables = True
        self.autodelete_table.blockSignals(True)
        self.autodelete_table.setUpdatesEnabled(False)
        self.autodelete_table.setRowCount(0)
        for value in values:
            self.add_autodelete_row(value)
        self.autodelete_table.blockSignals(False)
        self.autodelete_table.setUpdatesEnabled(True)
        self._loading_tables = False

    def collect_country_rows(self):
        countries = []
        for row in range(self.countries_table.rowCount()):
            country_item = self.countries_table.item(row, 0)
            iso_item = self.countries_table.item(row, 1)
            aliases_item = self.countries_table.item(row, 2)
            country = str(country_item.text() if country_item else '').strip()
            iso = normalize_country_code(iso_item.text() if iso_item else '')
            aliases_text = str(aliases_item.text() if aliases_item else '').strip()
            if not country:
                continue
            aliases = [
                part.strip()
                for part in aliases_text.split(',')
                if part.strip()
            ]
            countries.append({
                'country': country,
                'iso': iso,
                'aliases': aliases,
            })
        return countries

    def validate_country_rows(self):
        seen_codes = set()
        seen_names = set()
        for row in range(self.countries_table.rowCount()):
            country_item = self.countries_table.item(row, 0)
            iso_item = self.countries_table.item(row, 1)
            country = str(country_item.text() if country_item else '').strip()
            iso = normalize_country_code(iso_item.text() if iso_item else '')
            row_number = row + 1

            if not country:
                if country_item is None:
                    country_item = QTableWidgetItem('')
                    self.countries_table.setItem(row, 0, country_item)
                self.countries_table.setCurrentCell(row, 0)
                self.countries_table.selectRow(row)
                QMessageBox.warning(
                    self,
                    _('Countries'),
                    _('Country cannot be left blank.'),
                )
                self.countries_table.setFocus()
                self.countries_table.setCurrentCell(row, 0)
                self.countries_table.editItem(country_item)
                return False

            country_key = country.casefold()
            if country_key in seen_names:
                self.countries_table.setCurrentCell(row, 0)
                self.countries_table.selectRow(row)
                QMessageBox.warning(
                    self,
                    _('Countries'),
                    _('Country row {} uses a duplicate country name.').format(row_number),
                )
                return False
            seen_names.add(country_key)
            if iso and iso in seen_codes:
                self.countries_table.setCurrentCell(row, 1)
                self.countries_table.selectRow(row)
                QMessageBox.warning(
                    self,
                    _('Countries'),
                    _('Country row {} uses a duplicate ISO country code.').format(row_number),
                )
                return False
            if iso:
                seen_codes.add(iso)
        return True

    def collect_region_rows(self):
        regions = []
        valid_countries = {
            self.country_record_key(item['country'], item.get('iso', '')): item
            for item in self.collect_country_rows()
            if item.get('country')
        }
        for row in range(self.regions_table.rowCount()):
            combo = self.regions_table.cellWidget(row, 0)
            region_item = self.regions_table.item(row, 1)
            country_key = str(combo.currentData() if combo is not None else '')
            regions_text = str(region_item.text() if region_item else '').strip()
            if not country_key or not regions_text:
                continue
            country_record = valid_countries.get(country_key)
            if not country_record:
                continue
            for region in [part.strip() for part in regions_text.split(',') if part.strip()]:
                regions.append({
                    'country': country_record['country'],
                    'iso': country_record.get('iso', ''),
                    'region': region,
                })
        return regions

    def collect_autodelete_rows(self):
        rules = []
        for row in range(self.autodelete_table.rowCount()):
            rule = self.autodelete_rule_for_row(row)
            if rule:
                rules.append(rule)
        return rules

    def restore_user_json_defaults(self):
        defaults = build_default_user_data(
            country_name_language=self.country_name_language.currentData(),
            country_name_mode=self.current_country_name_mode(),
        )
        countries = list(defaults.get('countries', []) or [])
        regions = list(defaults.get('regions', []) or [])
        current_tab = self.tabs.currentWidget()

        if current_tab is self.countries_tab:
            self.load_country_rows(countries)
            self._countries_dirty = True
            return

        if current_tab is self.regions_tab:
            live_country_keys = {
                self.country_record_key(item['country'], item.get('iso', ''))
                for item in self.collect_country_rows()
                if item.get('country')
            }
            filtered_regions = [
                item for item in regions
                if self.country_record_key(item.get('country', ''), item.get('iso', '')) in live_country_keys
            ]
            self.load_region_rows(filtered_regions)
            self._regions_dirty = True
            return

        if current_tab is self.autodelete_tab:
            QMessageBox.information(
                self,
                _('Autodelete'),
                _('Auto-delete rules do not have defaults to restore.'),
            )
            return

        self.load_country_rows(countries)
        self.load_region_rows(regions)

        self._countries_dirty = True
        self._regions_dirty = True

    def save_settings(self):
        prefs['character_field'] = self.character_field.currentData()
        prefs['settings_field'] = self.settings_field.currentData()
        prefs['countries_field'] = self.countries_field.currentData()
        prefs['include_country_with_location'] = (
            self.include_country_with_location.isChecked()
        )
        prefs['keep_region_in_settings'] = (
            self.keep_region_in_settings.isChecked()
        )
        prefs['write_empty_to_custom_fields'] = (
            self.write_empty_to_custom_fields.isChecked()
        )
        prefs['country_name_language'] = self.country_name_language.currentData()
        prefs['country_name_mode'] = self.current_country_name_mode()
        prefs['query_interval_seconds'] = self.query_interval_seconds.value()
        prefs['max_books_per_job'] = self.max_books_per_job.value()
        prefs['autodelete_column_widths'] = self.current_autodelete_column_widths()

        if self._countries_dirty:
            save_user_country_data(self.collect_country_rows())
        if self._regions_dirty:
            save_user_region_data(self.collect_region_rows())
        if self._autodelete_dirty:
            save_user_autodelete_values(self.collect_autodelete_rows())

    def current_country_name_mode(self):
        if self.localize_country_names.isChecked():
            return COUNTRY_NAME_MODE_COUNTRY
        return COUNTRY_NAME_MODE_ALIAS

    def validate(self):
        return self.validate_country_rows()
