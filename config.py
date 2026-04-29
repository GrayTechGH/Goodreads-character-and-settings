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

from qt.core import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from calibre.utils.config import JSONConfig
from calibre_plugins.Goodreads_character_and_settings.settings_data import (
    COUNTRY_NAME_LANGUAGE_AUTO,
    COUNTRY_NAME_LANGUAGE_ENGLISH_FORMAL,
    COUNTRY_NAME_LANGUAGE_ENGLISH_SHORT,
    COUNTRY_NAME_MODE_ALIAS,
    COUNTRY_NAME_MODE_COUNTRY,
    build_default_user_data,
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


class ConfigWidget(QWidget):

    def __init__(self, custom_fields=None):
        QWidget.__init__(self)

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

        self.build_main_tab()
        self.build_countries_tab()
        self.build_regions_tab()
        self.build_autodelete_tab()
        self.build_footer()

        self.load_main_settings()
        self.load_country_rows(load_user_country_data())
        self.load_region_rows(load_user_region_data())
        self.load_autodelete_rows(load_user_autodelete_values())
        self.update_empty_option_state()

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
        self.countries_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
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
        self.regions_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
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
                    'them exactly.')
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        self.autodelete_table = QTableWidget(0, 1, self)
        self.autodelete_table.setHorizontalHeaderLabels([_('Value')])
        self.autodelete_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.autodelete_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.autodelete_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.autodelete_table.itemChanged.connect(self.autodelete_table_item_changed)
        layout.addWidget(self.autodelete_table)

        buttons = QHBoxLayout()
        self.add_autodelete_button = QPushButton(_('Add Value'), self)
        self.remove_autodelete_button = QPushButton(_('Remove Value'), self)
        self.add_autodelete_button.clicked.connect(self.add_autodelete_row)
        self.remove_autodelete_button.clicked.connect(self.remove_autodelete_row)
        buttons.addWidget(self.add_autodelete_button)
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
        row = self.countries_table.currentRow()
        if row >= 0:
            self.countries_table.removeRow(row)
            self.refresh_region_country_combos()
            if not self._loading_tables:
                self._countries_dirty = True

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
        row = self.regions_table.currentRow()
        if row >= 0:
            self.regions_table.removeRow(row)
            if not self._loading_tables:
                self._regions_dirty = True

    def add_autodelete_row(self, value=''):
        row = self.autodelete_table.rowCount()
        self.autodelete_table.insertRow(row)
        self.set_table_text(self.autodelete_table, row, 0, value)
        if not self._loading_tables:
            self._autodelete_dirty = True

    def remove_autodelete_row(self):
        row = self.autodelete_table.currentRow()
        if row >= 0:
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
        grouped = {}
        for item in regions:
            iso = normalize_country_code(item.get('iso', ''))
            country = item.get('country', '')
            region = item.get('region', '')
            if not country or not region:
                continue
            country_key = self.country_record_key(country, iso)
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
        for row, item in enumerate(self.collect_country_rows(), start=1):
            country_key = item.get('country', '').casefold()
            if country_key in seen_names:
                QMessageBox.warning(
                    self,
                    _('Countries'),
                    _('Country row {} uses a duplicate country name.').format(row),
                )
                return False
            seen_names.add(country_key)
            if item.get('iso') and item['iso'] in seen_codes:
                QMessageBox.warning(
                    self,
                    _('Countries'),
                    _('Country row {} uses a duplicate ISO country code.').format(row),
                )
                return False
            if item.get('iso'):
                seen_codes.add(item['iso'])
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
        values = []
        for row in range(self.autodelete_table.rowCount()):
            item = self.autodelete_table.item(row, 0)
            value = str(item.text() if item else '').strip()
            if value:
                values.append(value)
        return values

    def restore_user_json_defaults(self):
        defaults = build_default_user_data(
            country_name_language=self.country_name_language.currentData(),
            country_name_mode=self.current_country_name_mode(),
        )
        countries = list(defaults.get('countries', []) or [])
        regions = list(defaults.get('regions', []) or [])
        autodelete = list(defaults.get('autodelete', []) or [])
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
            self.load_autodelete_rows(autodelete)
            self._autodelete_dirty = True
            return

        self.load_country_rows(countries)
        self.load_region_rows(regions)
        self.load_autodelete_rows(autodelete)

        self._countries_dirty = True
        self._regions_dirty = True
        self._autodelete_dirty = True

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
