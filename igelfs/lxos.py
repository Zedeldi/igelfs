"""Module to assist handling LXOS firmware update files."""

import configparser
import logging
import os
import tempfile
import zipfile
from collections import OrderedDict
from collections.abc import Generator
from typing import Any

from igelfs.utils import tempfile_from_bytes

logger = logging.getLogger(__name__)


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

    def __init__(self, path: str | os.PathLike | None = None, *args, **kwargs) -> None:
        """Initialise instance of configuration parser."""
        super().__init__(
            *args,
            defaults=kwargs.pop("defaults", None),
            dict_type=kwargs.pop("dict_type", MultiDict),
            delimiters=kwargs.pop("delimiters", ("=",)),
            strict=kwargs.pop("strict", False),
            **kwargs,
        )  # type: ignore[call-overload]
        if path:
            logger.debug(f"Parsing configuration file '{path}'")
            self.read(path)

    @property
    def partitions(self) -> tuple[str, ...]:
        """Return tuple of keys for partitions."""
        return tuple(key for key in self if key.startswith("PART"))

    def get(self, *args, **kwargs) -> Any:
        """Override get method to strip values of quotes."""
        value = super().get(*args, **kwargs)
        return value.strip('"')

    def get_partition_minors_to_names(self) -> dict[int, str]:
        """Return dictionary of mapping of partition minors to names."""
        return {
            self.getint(partition, "number"): self.get(partition, "name")
            for partition in self.partitions
        }

    def find_partition_by_values(self, values: dict[str, str]) -> str | None:
        """Search for partition with matching values."""
        for partition in self.partitions:
            for key, value in values.items():
                if self.get(partition, key) != value:
                    break
            else:
                return partition
        return None

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


class FirmwareUpdate:
    """Class to manage firmware update archives."""

    def __init__(self, path: str | os.PathLike) -> None:
        """Initialise instance."""
        self.path = path

    @property
    def data(self) -> bytes:
        """Return bytes for update archive."""
        with open(self.path, "rb") as file:
            return file.read()

    def find_member(self, name: str) -> bytes:
        """Find member in archive and return extracted bytes."""
        logger.debug(f"Finding '{name}' in '{self.path}'")
        for prefix in ("lxos", "osiv"):
            try:
                return self.extract_member(f"{prefix}.{name}")
            except KeyError:
                continue
        raise KeyError(f"Member with name '{name}' not found in '{self.path}'")

    def extract_member(self, member: str | zipfile.ZipInfo) -> bytes:
        """Extract member from archive and return bytes."""
        logger.debug(f"Extracting '{member}' from '{self.path}'")
        with tempfile.TemporaryDirectory() as path:
            with zipfile.ZipFile(self.path, "r") as zip:
                extracted = zip.extract(member, path=path)
                with open(extracted, "rb") as file:
                    return file.read()

    def extract_all(self, path: str | os.PathLike) -> None:
        """Extract archive to path."""
        logger.debug(f"Extracting '{self.path}' to '{path}'")
        with zipfile.ZipFile(self.path, "r") as zip:
            zip.extractall(path)

    def get_partitions(self) -> Generator[tuple[int, bytes]]:
        """Return generator of tuples for partition minor to bytes."""
        data = self.find_member("inf")
        with tempfile_from_bytes(data) as path:
            config = LXOSParser(path)
            for partition_minor, name in config.get_partition_minors_to_names().items():
                try:
                    yield (partition_minor, self.find_member(name))
                except KeyError:
                    continue
