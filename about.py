#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2026, GrayTechGH'
__docformat__ = 'restructuredtext en'

from html import escape

try:
    load_translations()
except NameError:
    pass

try:
    _
except NameError:
    def _(text):
        return text


def build_about_text():
    from calibre_plugins.Goodreads_character_and_settings.__init__ import GoodreadsCharacterSettingsPlugin

    version = '.'.join(str(part) for part in GoodreadsCharacterSettingsPlugin.version)
    release_status = getattr(GoodreadsCharacterSettingsPlugin, 'release_status', '')
    minimum = '.'.join(str(part) for part in GoodreadsCharacterSettingsPlugin.minimum_calibre_version)

    version_line = _('Version {}').format(version)
    if release_status:
        version_line = '{} ({})'.format(version_line, release_status)

    translation_note = _(
        'Plugin-specific translations are machine-generated and may be imperfect. '
        'If you spot a mistake, corrections are welcome via {github} or the '
        '{mobileread}.'
    ).format(
        github='<a href="https://github.com/GrayTechGH/Goodreads-character-and-settings">GitHub</a>',
        mobileread='<a href="https://www.mobileread.com/forums/showthread.php?t=373260">MobileRead support thread</a>',
    )

    return ''.join([
        '<h3>{}</h3>'.format(escape(GoodreadsCharacterSettingsPlugin.name)),
        '<p>{}</p>'.format(escape(_('Created by {}').format(GoodreadsCharacterSettingsPlugin.author))),
        '<p>{}<br>{}</p>'.format(
            escape(version_line),
            escape(_('Requires calibre >= {}').format(minimum)),
        ),
        '<p>{}</p>'.format(translation_note),
    ])
