#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2026, GrayTechGH'
__docformat__ = 'restructuredtext en'

from calibre.gui2 import Dispatcher

from calibre_plugins.Goodreads_character_and_settings.common import cleanup_value
from calibre_plugins.Goodreads_character_and_settings.config import FIELD_NONE, FIELD_TAGS, prefs


class GoodreadsPreviewRunner(object):

    def __init__(self, gui, finished_callback=None):
        self.gui = gui
        self.finished_callback = finished_callback
        self.active_jobs = {}
        self.pending_jobs = 0
        self.completed_jobs = 0
        self.updated_count = 0
        self.failed_count = 0

    def run_for_selection(self):
        selected_books = self.get_selected_books()
        if not selected_books:
            self.show_status('No books selected.')
            self.finish()
            return

        books_with_ids = [
            book for book in selected_books
            if book['goodreads_id']
        ]

        if not books_with_ids:
            self.show_status('No selected books have a Goodreads id.')
            self.finish()
            return

        batch_size = max(1, int(prefs['max_books_per_job']))
        batches = chunk_books(books_with_ids, batch_size)
        self.active_jobs = {}
        self.pending_jobs = len(batches)
        self.completed_jobs = 0
        self.updated_count = 0
        self.failed_count = 0

        worker_options = {
            'query_interval_seconds': prefs['query_interval_seconds'],
            'include_country_with_location': prefs['include_country_with_location'],
            'keep_region_in_settings': prefs['keep_region_in_settings'],
            'debug_character_sources': prefs['debug_character_sources'],
            'debug_settings_pipeline': prefs['debug_settings_pipeline'],
            'write_empty_to_custom_fields': prefs['write_empty_to_custom_fields'],
            'field_specs': self.build_field_specs(),
            'retry_attempts': 3,
            'retry_delay_seconds': 2,
        }

        for index, batch in enumerate(batches, 1):
            description = (
                'Import Goodreads character and settings '
                '(job {} of {})'.format(index, len(batches))
            )
            job = self.gui.job_manager.run_job(
                Dispatcher(self.batch_job_finished),
                'arbitrary_n',
                args=[
                    'calibre_plugins.Goodreads_character_and_settings.worker_process',
                    'process_goodreads_batch',
                    (batch, worker_options),
                ],
                description=description,
            )
            self.active_jobs[job] = len(batch)

        self.show_status(
            'Starting Goodreads character and settings for {} book(s) in {} job(s).'.format(
                len(books_with_ids),
                len(batches),
            )
        )

    def get_selected_books(self):
        library_view = getattr(self.gui, 'library_view', None)
        if library_view is None:
            return []

        selection_model = library_view.selectionModel()
        if selection_model is None:
            return []

        rows = selection_model.selectedRows()
        if not rows:
            return []

        model = library_view.model()
        db = self.gui.current_db
        books = []
        for row in rows:
            book_id = model.id(row)
            mi = db.get_metadata(book_id, index_is_id=True)
            identifiers = get_metadata_identifiers(mi)
            books.append({
                'book_id': book_id,
                'title': mi.title or 'Unknown Title',
                'author': format_authors(getattr(mi, 'authors', None)),
                'goodreads_id': clean_goodreads_id(identifiers.get('goodreads')),
                'existing_fields': self.get_existing_destination_values(db, mi),
            })
        return books

    def build_field_specs(self):
        db = self.gui.current_db
        field_metadata = getattr(db, 'field_metadata', {})
        specs = {}
        for pref_name in ('character_field', 'settings_field', 'countries_field'):
            field_name = prefs[pref_name]
            metadata = field_metadata.get(field_name, {}) if field_name not in (FIELD_NONE, FIELD_TAGS) else {}
            specs[pref_name] = {
                'field_name': field_name,
                'is_tags': field_name == FIELD_TAGS,
                'is_multiple': bool(metadata.get('is_multiple')),
            }
        return specs

    def get_existing_destination_values(self, db, mi):
        existing = {}
        for field_name in {
            prefs['character_field'],
            prefs['settings_field'],
            prefs['countries_field'],
        }:
            if field_name == FIELD_NONE or field_name in existing:
                continue
            existing[field_name] = get_existing_field_values_from_metadata(db, mi, field_name)
        return existing

    def apply_field_updates(self, updates_by_field):
        db = self.gui.current_db
        new_api = getattr(db, 'new_api', None)
        if new_api is not None and hasattr(new_api, 'set_field'):
            for field_name, payloads in updates_by_field.items():
                if not payloads:
                    continue
                new_api.set_field(field_name, payloads)
            return

        for field_name, payloads in updates_by_field.items():
            for book_id, payload in payloads.items():
                self.apply_field_update_legacy(db, book_id, field_name, payload)

    def apply_field_update_legacy(self, db, book_id, field_name, payload):
        mi = db.get_metadata(book_id, index_is_id=True)
        setter = getattr(mi, 'set', None)
        if callable(setter):
            setter(field_name, payload)
        else:
            setattr(mi, field_name, payload)
        db.set_metadata(book_id, mi, set_title=False, set_authors=False, commit=True)

    def refresh_gui(self, updated_book_ids, recount_tags_view=False):
        if not updated_book_ids:
            return
        library_view = getattr(self.gui, 'library_view', None)
        model = getattr(library_view, 'model', lambda: None)()
        current_index = getattr(library_view, 'currentIndex', lambda: None)() if library_view is not None else None
        current_row = (
            current_index.row()
            if current_index is not None and hasattr(current_index, 'isValid') and current_index.isValid()
            else None
        )
        if model is not None and hasattr(model, 'refresh_ids'):
            if current_row is None:
                model.refresh_ids(list(updated_book_ids))
            else:
                model.refresh_ids(list(updated_book_ids), current_row)
        elif model is not None and hasattr(model, 'refresh'):
            model.refresh()
        if (
            model is not None
            and current_index is not None
            and hasattr(current_index, 'isValid')
            and current_index.isValid()
            and hasattr(model, 'current_changed')
        ):
            model.current_changed(current_index, current_index)
        refresh_cover_browser = getattr(self.gui, 'refresh_cover_browser', None)
        if callable(refresh_cover_browser):
            refresh_cover_browser()
        if library_view is not None:
            viewport = getattr(library_view, 'viewport', lambda: None)()
            if viewport is not None and hasattr(viewport, 'update'):
                viewport.update()
            if current_index is not None and hasattr(current_index, 'isValid') and current_index.isValid():
                visual_rect = getattr(library_view, 'visualRect', lambda *_args: None)(current_index)
                if visual_rect is not None and viewport is not None and hasattr(viewport, 'update'):
                    viewport.update(visual_rect)
        if recount_tags_view:
            tags_view = getattr(self.gui, 'tags_view', None)
            if tags_view is not None and hasattr(tags_view, 'recount_with_position_based_index'):
                tags_view.recount_with_position_based_index()
            elif tags_view is not None and hasattr(tags_view, 'recount'):
                tags_view.recount()

    def show_status(self, message, timeout=5000):
        status_bar = getattr(self.gui, 'status_bar', None)
        if status_bar is not None and hasattr(status_bar, 'show_message'):
            status_bar.show_message(message, timeout)

    def batch_job_finished(self, job):
        batch_size = self.active_jobs.pop(job, 0)
        self.completed_jobs += 1

        if job.failed:
            self.failed_count += batch_size
        else:
            updates_by_field = {}
            batch_updated_book_ids = set()
            batch_recount_tags = False
            for result in job.result or []:
                if result.get('error'):
                    self.failed_count += 1
                    continue
                try:
                    for field_name, payload in result.get('field_updates', {}).items():
                        updates_by_field.setdefault(field_name, {})[result['book_id']] = payload
                        batch_updated_book_ids.add(result['book_id'])
                        if field_name == FIELD_TAGS:
                            batch_recount_tags = True
                    if prefs.get('debug_character_sources') and result.get('debug_characters'):
                        print('Goodreads character debug for book {}: {}'.format(
                            result['book_id'],
                            result['debug_characters'],
                        ), flush=True)
                    if prefs.get('debug_settings_pipeline') and result.get('debug_settings'):
                        print('Goodreads settings debug for book {}: {}'.format(
                            result['book_id'],
                            result['debug_settings'],
                        ), flush=True)
                    self.updated_count += 1
                except Exception:
                    self.failed_count += 1
            if updates_by_field:
                self.apply_field_updates(updates_by_field)
                self.refresh_gui(
                    batch_updated_book_ids,
                    recount_tags_view=batch_recount_tags,
                )
        if self.completed_jobs >= self.pending_jobs:
            self.show_status(
                'Goodreads character and settings updated {} book(s); {} failed.'.format(
                    self.updated_count,
                    self.failed_count,
                ),
                timeout=7000,
            )
            self.finish()

    def finish(self):
        if callable(self.finished_callback):
            callback = self.finished_callback
            self.finished_callback = None
            callback()


def chunk_books(books, batch_size):
    return [
        books[index:index + batch_size]
        for index in range(0, len(books), batch_size)
    ]


def normalize_field_values(value, metadata=None):
    metadata = metadata or {}
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        normalized = []
        for item in value:
            cleaned = cleanup_value(item)
            if cleaned:
                normalized.append(cleaned)
        return normalized
    if isinstance(value, str):
        cleaned = cleanup_value(value)
        return [cleaned] if cleaned else []

    cleaned = cleanup_value(value)
    return [cleaned] if cleaned else []


def get_existing_field_values_from_metadata(db, mi, field_name):
    if field_name == FIELD_TAGS:
        return list(getattr(mi, 'tags', None) or [])

    metadata = getattr(db, 'field_metadata', {}).get(field_name, {})
    getter = getattr(mi, 'get', None)
    if callable(getter):
        current_value = getter(field_name)
    else:
        current_value = getattr(mi, field_name, None)
    return normalize_field_values(current_value, metadata)


def get_metadata_identifiers(mi):
    getter = getattr(mi, 'get_identifiers', None)
    if callable(getter):
        return getter() or {}
    return getattr(mi, 'identifiers', {}) or {}


def clean_goodreads_id(value):
    if value is None:
        return None
    text = cleanup_value(value)
    if not text:
        return None
    import re
    match = re.search(r'(\d+)', text)
    return match.group(1) if match else None


def format_authors(authors):
    if not authors:
        return 'Unknown Author'
    return ' & '.join(authors)
