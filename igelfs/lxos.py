"""Module to assist handling LXOS firmware update files."""

import configparser
from collections import OrderedDict
from pathlib import Path
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

    def __init__(self, path: str | Path | None = None, *args, **kwargs) -> None:
        """Initialise instance of configuration parser."""
        super().__init__(
            *args,
            defaults=kwargs.pop("defaults", None),
            dict_type=kwargs.pop("dict_type", MultiDict),
            delimiters=kwargs.pop("delimiters", ("=",)),
            strict=kwargs.pop("strict", False),
            **kwargs,
        )
        if path:
            self.read(path)

    @property
    def partitions(self) -> tuple[str]:
        """Return tuple of keys for partitions."""
        return tuple(key for key in self if key.startswith("PART"))

    def get(self, *args, **kwargs) -> Any:
        """Override get method to strip values of quotes."""
        value = super().get(*args, **kwargs)
        return value.strip('"')

    def find_partition_by_values(self, values: dict[str, str]) -> str:
        """Search for partition with matching values."""
        for partition in self.partitions:
            for key, value in values.items():
                if self.get(partition, key) != value:
                    break
            else:
                return partition

    def find_partition_minor_by_name(self, name: str) -> int | None:
        """Return partition minor by specified name."""
        for key in self.partitions:
            if self.get(key, "name") == name:
                return self.getint(key, "number")
        return None

    def find_name_by_partition_minor(self, partition_minor: int) -> str | None:
        """Return name by specified partition minor."""
        for key in self.partitions:
            if self.getint(key, "number") == partition_minor:
                return self.get(key, "name")
        return None
