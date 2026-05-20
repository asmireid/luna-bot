import configparser


class Config:
    _instances: dict[str, "Config"] = {}

    def __new__(cls, config_file: str = 'config/config.ini'):
        if config_file not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[config_file] = instance
            instance._initialized = False
        return cls._instances[config_file]

    def __init__(self, config_file='config/config.ini'):
        if getattr(self, '_initialized', False):
            return
        self.config_file = config_file
        self.config = self.load_config()
        self._generate_properties()
        self._initialized = True

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