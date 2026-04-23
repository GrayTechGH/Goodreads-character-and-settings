from time import sleep

from qt.core import QAction, QMenu

from calibre.gui2 import error_dialog, info_dialog
from calibre.gui2.actions import InterfaceAction

from calibre_plugins.goodreads_character_and_settings.config import PREFS, TAGS_TARGET
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
        chars_target = PREFS['characters_column']
        settings_target = PREFS['settings_column']
        empty_for_custom_fields = bool(PREFS['empty_for_custom_fields'])
        query_delay_seconds = int(PREFS['query_delay_seconds'] or 30)

        if not chars_target and not settings_target:
            error_dialog(
                self.gui,
                'No destinations configured',
                'Configure at least one destination before running this action.',
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

        for i, row in enumerate(rows):
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
            if chars_target:
                value = self._build_value(db, book_id, chars_target, characters, empty_for_custom_fields)
                if value is not None:
                    values[chars_target] = value
            if settings_target:
                value = self._build_value(db, book_id, settings_target, settings, empty_for_custom_fields)
                if value is not None:
                    values[settings_target] = value

            if not values:
                skipped += 1
                continue

            self._set_custom_values(db, book_id, values)
            touched_ids.append(book_id)
            updated += 1

            if query_delay_seconds > 0 and i < len(rows) - 1:
                sleep(query_delay_seconds)

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
            if field == TAGS_TARGET and hasattr(db, 'set_tags'):
                db.set_tags(book_id, value, append=False)
                continue
            if field == TAGS_TARGET:
                continue
            db.set_custom(book_id, value, label=field)

    def _build_value(self, db, book_id, field, items, empty_for_custom_fields):
        cleaned_items = [x for x in items if x.strip().lower() != 'empty']

        if field == TAGS_TARGET:
            if not cleaned_items:
                return None
            existing_tags = self._get_existing_tags(db, book_id)
            return self._dedupe(existing_tags + cleaned_items)

        if cleaned_items:
            return ', '.join(cleaned_items)

        if empty_for_custom_fields:
            return 'Empty'

        return None

    def _get_existing_tags(self, db, book_id):
        if hasattr(db, 'new_api') and hasattr(db.new_api, 'field_for'):
            tags = db.new_api.field_for('tags', book_id) or []
            return [tag for tag in tags if tag and tag.strip().lower() != 'empty']
        mi = db.get_metadata(book_id, index_is_id=True)
        return [tag for tag in (mi.tags or []) if tag and tag.strip().lower() != 'empty']

    @staticmethod
    def _dedupe(items):
        seen = set()
        out = []
        for item in items:
            if item not in seen:
                out.append(item)
                seen.add(item)
        return out
