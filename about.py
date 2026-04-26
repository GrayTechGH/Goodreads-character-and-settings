#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2026, GrayTechGH'
__docformat__ = 'restructuredtext en'


def build_about_text():
    from calibre_plugins.Goodreads_character_and_settings.__init__ import InterfacePluginDemo

    version = '.'.join(str(part) for part in InterfacePluginDemo.version)
    release_status = getattr(InterfacePluginDemo, 'release_status', '')
    minimum = '.'.join(str(part) for part in InterfacePluginDemo.minimum_calibre_version)

    version_line = 'Version {}'.format(version)
    if release_status:
        version_line = '{} ({})'.format(version_line, release_status)

    return '\n'.join([
        InterfacePluginDemo.name,
        '=' * len(InterfacePluginDemo.name),
        '',
        'Created by {}'.format(InterfacePluginDemo.author),
        '',
        version_line,
        'Requires calibre >= {}'.format(minimum),
    ])
