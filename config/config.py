import configparser


class Config:
    _instance = None

    def __new__(cls, config_file: str = "config/config.ini"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_file: str = "config/config.ini"):
        if self._initialized:
            return
        self._file = config_file
        self._parser = configparser.ConfigParser()
        self._parser.read(config_file, encoding="utf-8")
        self._values: dict[str, object] = {}
        self._sections: dict[str, str] = {}  # key -> section name
        self._load()
        self._initialized = True

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        for section in self._parser.sections():
            for option in self._parser.options(section):
                key = option
                self._values[key] = self._coerce(self._parser.get(section, option))
                self._sections[key] = section

    @staticmethod
    def _coerce(value: str) -> object:
        v = value.strip()
        if v.lower() in ("true", "false"):
            return v.lower() == "true"
        try:
            return int(v) if "." not in v else float(v)
        except ValueError:
            return v

    def _save(self) -> None:
        with open(self._file, "w", encoding="utf-8") as f:
            self._parser.write(f)

    # ------------------------------------------------------------------
    # public API (backward-compatible with old property-based interface)
    # ------------------------------------------------------------------

    def __getattr__(self, name: str) -> object:
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._values:
            return self._values[name]
        raise AttributeError(f"'{type(self).__name__}' has no config key '{name}'")

    def __setattr__(self, name: str, value: object) -> None:
        if name.startswith("_"):
            super().__setattr__(name, value)
            return
        self._values[name] = value
        section = self._sections.get(name, "settings")
        if section not in self._parser:
            self._parser.add_section(section)
        self._parser.set(section, name, str(value))
        self._sections[name] = section
        self._save()

    def __dir__(self) -> list[str]:
        return list(self._values.keys()) + list(super().__dir__())

    def is_sensitive(self, option: str) -> bool:
        """True when *option* belongs to the [credentials] section."""
        return self._sections.get(option, "") == "credentials"

    def list_options(self) -> dict[str, object]:
        """Return every non-sensitive key/value pair (for ``!list_config``)."""
        return {k: v for k, v in self._values.items() if not self.is_sensitive(k)}
