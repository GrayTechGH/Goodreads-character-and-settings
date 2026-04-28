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

# The class that all Interface Action plugin wrappers must inherit from
from calibre.customize import InterfaceActionBase


class GoodreadsCharacterSettingsPlugin(InterfaceActionBase):
    '''
    This class is a simple wrapper that provides information about the actual
    plugin class. The actual interface plugin class is called InterfacePlugin
    and is defined in the ui.py file, as specified in the actual_plugin field
    below.

    The reason for having two classes is that it allows the command line
    calibre utilities to run without needing to load the GUI libraries.
    '''
    name                = _('Goodreads character and settings')
    description         = _('Plugin that imports character and settings data from Goodreads and writes it to custom fields')
    supported_platforms = ['windows', 'osx', 'linux']
    author              = 'GrayTechGH'
    version             = (1, 0, 1)
    minimum_calibre_version = (0, 7, 53)

    #: This field defines the GUI plugin class that contains all the code
    #: that actually does something. Its format is module_path:class_name
    #: The specified class must be defined in the specified module.
    actual_plugin       = 'calibre_plugins.Goodreads_character_and_settings.ui:InterfacePlugin'

    def is_customizable(self):
        '''
        This method must return True to enable customization via
        Preferences->Plugins
        '''
        return True

    def config_widget(self):
        '''
        Implement this method and :meth:`save_settings` in your plugin to
        use a custom configuration dialog.

        This method, if implemented, must return a QWidget. The widget can have
        an optional method validate() that takes no arguments and is called
        immediately after the user clicks OK. Changes are applied if and only
        if the method returns True.

        If for some reason you cannot perform the configuration at this time,
        return a tuple of two strings (message, details), these will be
        displayed as a warning dialog to the user and the process will be
        aborted.

        The base class implementation of this method raises NotImplementedError
        so by default no user configuration is possible.
        '''
        # It is important to put this import statement here rather than at the
        # top of the module as importing the config class will also cause the
        # GUI libraries to be loaded, which we do not want when using calibre
        # from the command line
        from calibre_plugins.Goodreads_character_and_settings.config import ConfigWidget
        custom_fields = []
        ac = self.actual_plugin_
        if ac is not None:
            custom_fields = get_custom_fields(ac.gui.current_db)
        return ConfigWidget(custom_fields=custom_fields)

    def save_settings(self, config_widget):
        '''
        Save the settings specified by the user with config_widget.

        :param config_widget: The widget returned by :meth:`config_widget`.
        '''
        config_widget.save_settings()

        # Apply the changes
        ac = self.actual_plugin_
        if ac is not None:
            ac.apply_settings()


def get_custom_fields(db):
    field_metadata = getattr(db, 'field_metadata', {})
    custom_fields = []
    for lookup_name in sorted(getattr(db, 'custom_field_keys', lambda: [])()):
        metadata = field_metadata.get(lookup_name, {})
        name = metadata.get('name', lookup_name)
        display_name = '{} ({})'.format(name, lookup_name)
        custom_fields.append((lookup_name, display_name))
    return custom_fields
