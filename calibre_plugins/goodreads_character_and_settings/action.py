from qt.core import QAction, QMenu

from calibre.gui2 import error_dialog, info_dialog
from calibre.gui2.actions import InterfaceAction

from calibre_plugins.goodreads_character_and_settings.config import PREFS
from calibre_plugins.goodreads_character_and_settings.goodreads import (
    extract_characters_and_settings,
    fetch_book_page,
)


class GoodreadsCharacterAndSettingsAction(InterfaceAction):
    name = 'Goodreads Character and Settings'
    action_spec = (
        'Populate Goodreads Characters/Settings',
        None,
        'Fetch characters and settings from Goodreads for selected books',
        None,
    )

    def genesis(self):
        self.qaction.triggered.connect(self.populate_selected_books)

        menu = QMenu(self.gui)
        run_action = QAction('Populate selected books', self.gui)
        run_action.triggered.connect(self.populate_selected_books)
        menu.addAction(run_action)

        config_action = QAction('Configure columns...', self.gui)
        config_action.triggered.connect(self.show_configuration)
        menu.addAction(config_action)

        self.qaction.setMenu(menu)

    def show_configuration(self):
        self.interface_action_base_plugin.do_user_config(self.gui)

    def populate_selected_books(self):
        chars_col = PREFS['characters_column']
        settings_col = PREFS['settings_column']
        if not chars_col and not settings_col:
            error_dialog(
                self.gui,
                'No columns configured',
                'Configure at least one custom column before running this action.',
                show=True,
            )
            return

        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows:
            error_dialog(self.gui, 'No books selected', 'Please select one or more books.', show=True)
            return

        db = self.gui.current_db
        model = self.gui.library_view.model()
        updated = 0
        skipped = 0
        errors = []
        touched_ids = []

        for row in rows:
            book_id = model.id(row)
            mi = db.get_metadata(book_id, index_is_id=True)
            gr_id = (mi.identifiers or {}).get('goodreads')
            if not gr_id:
                skipped += 1
                continue

            try:
                html = fetch_book_page(gr_id)
                characters, settings = extract_characters_and_settings(html)
            except Exception as exc:
                errors.append(f'{mi.title}: {exc}')
                continue

            values = {}
            if chars_col and characters:
                values[chars_col] = ', '.join(characters)
            if settings_col and settings:
                values[settings_col] = ', '.join(settings)

            if not values:
                skipped += 1
                continue

            self._set_custom_values(db, book_id, values)
            touched_ids.append(book_id)
            updated += 1

        db.commit()
        if touched_ids:
            model.refresh_ids(touched_ids, current_row=self.gui.library_view.currentIndex().row())

        message = f'Updated: {updated}\nSkipped: {skipped}'
        if errors:
            message += '\n\nErrors:\n' + '\n'.join(errors[:10])
        info_dialog(self.gui, 'Goodreads import complete', message, show=True)

    def _set_custom_values(self, db, book_id, values):
        if hasattr(db, 'new_api') and hasattr(db.new_api, 'set_field'):
            for field, value in values.items():
                db.new_api.set_field(field, {book_id: value})
            return

        # Older calibre fallback.
        for field, value in values.items():
            db.set_custom(book_id, value, label=field)
