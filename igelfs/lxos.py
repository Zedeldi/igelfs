"""Module to assist handling LXOS firmware update files."""

import configparser
from collections import OrderedDict
from typing import Any


class MultiDict(OrderedDict):
    """OrderedDict subclass to allow reading INI file with non-unique keys."""

    _unique: int = 0

    def __setitem__(self, key: str, value: Any):
        """Override set item method to modify partition names."""
        if key == "PART" and isinstance(value, dict):
            self._unique += 1
            key += str(self._unique)
        super().__setitem__(key, value)


class LXOSParser(configparser.ConfigParser):
    """ConfigParser subclass for LXOS configuration files."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialise instance of configuration parser."""
        super().__init__(
            *args,
            defaults=kwargs.pop("defaults", None),
            dict_type=kwargs.pop("dict_type", MultiDict),
            delimiters=kwargs.pop("delimiters", ("=",)),
            strict=kwargs.pop("strict", False),
            **kwargs,
        )

    def get(self, *args, **kwargs) -> Any:
        """Override get method to strip values of quotes."""
        value = super().get(*args, **kwargs)
        return value.strip('"')
