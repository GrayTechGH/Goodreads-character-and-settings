from calibre.customize import InterfaceActionBase


class GoodreadsCharacterAndSettingsPlugin(InterfaceActionBase):
    name = 'Goodreads Character and Settings'
    description = 'Populate character and setting custom columns from Goodreads.'
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Codex'
    version = (0, 1, 0)
    minimum_calibre_version = (6, 0, 0)

    actual_plugin = 'calibre_plugins.goodreads_character_and_settings.action:GoodreadsCharacterAndSettingsAction'

    def is_customizable(self):
        return True

    def config_widget(self):
        from calibre_plugins.goodreads_character_and_settings.config import ConfigWidget

        return ConfigWidget(self)

    def save_settings(self, config_widget):
        config_widget.save_settings()
