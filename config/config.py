import configparser


class Config:
    def __init__(self, config_file='config/config.ini'):
        self.config_file = config_file
        self.config = self.load_config()
        self._generate_properties()

    def load_config(self):
        config = configparser.ConfigParser()
        config.read(self.config_file, encoding='utf-8')
        return config

    def save_config(self):
        with open(self.config_file, 'w', encoding='utf-8') as configfile:
            self.config.write(configfile)

    def _determine_type(self, value):
        """Determine the type of a value based on its content."""
        if value.lower() in ['true', 'false']:
            return bool(value.lower() == 'true')
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            return value  # Default to string if no conversion is possible

    def _generate_properties(self):
        for section in self.config.sections():
            for option in self.config.options(section):
                prop_name = f"{option}".lower()
                def getter(self, section=section, option=option):
                    raw_value = self.config.get(section, option)
                    return self._determine_type(raw_value)

                def setter(self, value, section=section, option=option):
                    self.config.set(section, option, str(value))
                    self.save_config()
                
                setattr(
                    self.__class__,
                    prop_name,
                    property(getter, setter)
                )

    def is_sensitive(self, option):
        return option in self.config['credentials']

    # @property
    # def bot_token(self):
    #     return self.config.get('credentials', 'bot_token')

    # @bot_token.setter
    # def bot_token(self, value):
    #     self.config.set('credentials', 'bot_token', value)
    #     self.save_config()

    # @property
    # def bot_name(self):
    #     return self.config.get('customizations', 'bot_name')

    # @bot_name.setter
    # def bot_name(self, value):
    #     self.config.set('customizations', 'bot_name', value)
    #     self.save_config()

    # @property
    # def bot_activity(self):
    #     return self.config.get('customizations', 'bot_activity')

    # @bot_activity.setter
    # def bot_activity(self, value):
    #     self.config.set('customizations', 'bot_activity', value)
    #     self.save_config()

    # @property
    # def footer(self):
    #     return self.config.get('customizations', 'embed_footer')

    # @footer.setter
    # def footer(self, value):
    #     self.config.set('customizations', 'embed_footer', value)
    #     self.save_config()

    # @property
    # def wait_message(self):
    #     return self.config.get('customizations', 'wait_message')

    # @wait_message.setter
    # def wait_message(self, value):
    #     self.config.set('customizations', 'wait_message', value)
    #     self.save_config()

    # @property
    # def command_prefix(self):
    #     return self.config.get('settings', 'command_prefix')

    # @command_prefix.setter
    # def command_prefix(self, value):
    #     self.config.set('settings', 'command_prefix', value)
    #     self.save_config()

    # @property
    # def display_confirmation(self):
    #     return self.config.getboolean('settings', 'display_confirmation')

    # @display_confirmation.setter
    # def display_confirmation(self, value):
    #     self.config.set('settings', 'display_confirmation', value)
    #     self.save_config()

    # @property
    # def delete_confirmation(self):
    #     return self.config.getboolean('settings', 'delete_confirmation')

    # @delete_confirmation.setter
    # def delete_confirmation(self, value):
    #     self.config.set('settings', 'delete_confirmation', value)
    #     self.save_config()

    # @property
    # def wait_time(self):
    #     return self.config.getint('settings', 'seconds_before_deleting_confirmation')

    # @wait_time.setter
    # def wait_time(self, value):
    #     self.config.set('settings', 'seconds_before_deleting_confirmation', value)
    #     self.save_config()

    # @property
    # def reply(self):
    #     return self.config.getboolean('settings', 'reply')

    # @reply.setter
    # def reply(self, value):
    #     self.config.set('settings', 'reply', value)
    #     self.save_config()

    # @property
    # def mention_author(self):
    #     return self.config.getboolean('settings', 'mention_author')

    # @mention_author.setter
    # def mention_author(self, value):
    #     self.config.set('settings', 'mention_author', value)
    #     self.save_config()

    # @property
    # def delete_invocation(self):
    #     return self.config.getboolean('settings', 'delete_invocation')

    # @delete_invocation.setter
    # def delete_invocation(self, value):
    #     self.config.set('settings', 'delete_invocation', value)
    #     self.save_config()

    # @property
    # def ephemeral(self):
    #     return self.config.getboolean('settings', 'ephemeral')

    # @ephemeral.setter
    # def ephemeral(self, value):
    #     self.config.set('settings', 'ephemeral', value)
    #     self.save_config()

    # @property
    # def nai_username(self):
    #     return self.config.get('credentials', 'nai_username')

    # @property
    # def nai_password(self):
    #     return self.config.get('credentials', 'nai_password')

    # @property
    # def uc_preset(self):
    #     return self.config.get('painting_settings', 'uc_preset')

    # @uc_preset.setter
    # def uc_preset(self, value):
    #     self.config.set('painting_settings', 'uc_preset', value)
    #     self.save_config()

    # @property
    # def sampler(self):
    #     return self.config.get('painting_settings', 'sampler')

    # @sampler.setter
    # def sampler(self, value):
    #     self.config.set('painting_settings', 'sampler', value)
    #     self.save_config()

    # @property
    # def uc_base(self):
    #     return self.config.get('painting_settings', 'uc_base')

    # @uc_base.setter
    # def uc_base(self, value):
    #     self.config.set('painting_settings', 'uc_base', value)
    #     self.save_config()

    # @property
    # def seed(self):
    #     return self.config.getint('painting_settings', 'seed')

    # @seed.setter
    # def seed(self, value):
    #     self.config.set('painting_settings', 'seed', value)
    #     self.save_config()

    # @property
    # def resolution(self):
    #     return self.config.get('painting_settings', 'resolution')

    # @resolution.setter
    # def resolution(self, value):
    #     self.config.set('painting_settings', 'resolution', value)
    #     self.save_config()

    # @property
    # def prompt_prefix(self):
    #     return self.config.get('painting_settings', 'prompt_prefix')

    # @prompt_prefix.setter
    # def prompt_prefix(self, value):
    #     self.config.set('painting_settings', 'prompt_prefix', value)
    #     self.save_config()

    # @property
    # def decrisper(self):
    #     return self.config.getboolean('painting_settings', 'decrisper')

    # @decrisper.setter
    # def decrisper(self, value):
    #     self.config.set('painting_settings', 'decrisper', value)
    #     self.save_config()

    # @property
    # def quality_toggle(self):
    #     return self.config.getboolean('painting_settings', 'quality_toggle')

    # @quality_toggle.setter
    # def quality_toggle(self, value):
    #     self.config.set('painting_settings', 'quality_toggle', value)
    #     self.save_config()

    # @property
    # def speaker(self):
    #     return self.config.get('tts_settings', 'speaker')

    # @speaker.setter
    # def speaker(self, value):
    #     self.config.set('tts_settings', 'speaker', value)
    #     self.save_config()

    # @property
    # def openai_api_key(self):
    #     return self.config.get('credentials', 'openai_api_key')

    # @property
    # def api_url(self):
    #     return self.config.get('chat_settings', 'api_url')

    # @api_url.setter
    # def api_url(self, value):
    #     self.config.set('chat_settings', 'api_url', value)
    #     self.save_config()

    # @property
    # def temperature(self):
    #     return self.config.getfloat('chat_settings', 'temperature')

    # @temperature.setter
    # def temperature(self, value):
    #     self.config.set('chat_settings', 'temperature', value)
    #     self.save_config()

    # @property
    # def top_p(self):
    #     return self.config.getfloat('chat_settings', 'top_p')

    # @top_p.setter
    # def top_p(self, value):
    #     self.config.set('chat_settings', 'top_p', value)
    #     self.save_config()

    # @property
    # def top_k(self):
    #     return self.config.getint('chat_settings', 'top_k')

    # @top_k.setter
    # def top_k(self, value):
    #     self.config.set('chat_settings', 'top_k', value)
    #     self.save_config()

    # @property
    # def max_new_tokens(self):
    #     return self.config.getint('chat_settings', 'max_new_tokens')

    # @max_new_tokens.setter
    # def max_new_tokens(self, value):
    #     self.config.set('chat_settings', 'max_new_tokens', value)
    #     self.save_config()

    # @property
    # def model(self):
    #     return self.config.get('chat_settings', 'model')

    # @model.setter
    # def model(self, value):
    #     self.config.set('chat_settings', 'model', value)

    # @property
    # def context_limit(self):
    #     return self.config.getint('chat_settings', 'context_limit')

    # @context_limit.setter
    # def context_limit(self, value):
    #     self.config.set('chat_settings', 'context_limit', value)

    # @property
    # def system_prompt(self):
    #     return self.config.get('chat_settings', 'system_prompt')

    # @system_prompt.setter
    # def system_prompt(self, value):
    #     self.config.set('chat_settings', 'system_prompt', value)
    #     self.save_config()
