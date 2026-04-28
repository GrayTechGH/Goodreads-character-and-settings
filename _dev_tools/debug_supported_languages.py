#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2026, GrayTechGH'
__docformat__ = 'restructuredtext en'


def main():
    from calibre.utils.localization import available_translations, get_lang

    active_language = get_lang()
    supported_languages = sorted(set(available_translations()) | {'en'})

    print('Active language: {}'.format(active_language))
    print('Supported language count: {}'.format(len(supported_languages)))
    print('Supported languages:')
    for language in supported_languages:
        print(language)


if __name__ == '__main__':
    main()
