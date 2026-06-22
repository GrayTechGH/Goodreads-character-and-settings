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

from qt.core import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QVBoxLayout

from calibre_plugins.Goodreads_character_and_settings.config import prefs


class GoodreadsDebugDialog(QDialog):

    def __init__(self, parent):
        QDialog.__init__(self, parent)
        self.setWindowTitle(_('Goodreads Debug'))

        layout = QVBoxLayout()
        self.setLayout(layout)

        form = QFormLayout()
        layout.addLayout(form)

        self.simulated_error = QComboBox(self)
        self.simulated_error.addItem(_('Disabled'), '')
        self.simulated_error.addItem(_('Browser challenge (HTTP 202)'), 'waf_challenge')
        self.simulated_error.addItem(_('Book not found (HTTP 404)'), 'not_found')
        self.simulated_error.addItem(_('Access denied (HTTP 403)'), 'access_denied')
        self.simulated_error.addItem(_('Rate limited (HTTP 429)'), 'rate_limited')
        self.simulated_error.addItem(_('No book data (HTTP 200)'), 'missing_book_data')
        saved_value = prefs.get('debug_simulated_error', '')
        index = self.simulated_error.findData(saved_value)
        self.simulated_error.setCurrentIndex(index if index >= 0 else 0)
        form.addRow(_('Simulate Goodreads error:'), self.simulated_error)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
