"""Module to access and parse IGEL OS registry."""

import gzip
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from igelfs.device import Cryptsetup, Mount
from igelfs.filesystem import Filesystem
from igelfs.models import Section
from igelfs.utils import tempfile_from_bytes

try:
    from igelfs.kml import Keyring
except ImportError:
    _KEYRING_AVAILABLE = False
else:
    _KEYRING_AVAILABLE = True

type ElementDict = dict[ElementTree.Element, ElementDict | str | None]
type RecursiveDict = dict[str, RecursiveDict | Any]


class XmlHelper:
    """Helper class for generic XML methods."""

    @classmethod
    def to_dict(cls: type["XmlHelper"], element: ElementTree.Element) -> ElementDict:
        """Return dictionary of children for element."""
        return {
            child: (
                children
                if (children := cls.to_dict(child))
                else (child.text.strip() if child.text else child.text)
            )
            for child in element
        }

    @classmethod
    def convert_elements_to_strings(
        cls: type["XmlHelper"], elements: ElementDict
    ) -> RecursiveDict:
        """Convert dictionary of elements to strings."""
        return {
            key.tag: (
                cls.convert_elements_to_strings(value)
                if isinstance(value, dict)
                else value
            )
            for key, value in elements.items()
        }

    @classmethod
    def convert_xml_types(
        cls: type["XmlHelper"], elements: RecursiveDict
    ) -> RecursiveDict:
        """Convert strings in dictionary to Python types."""
        return {
            key: (
                cls.convert_xml_types(value)
                if isinstance(value, dict)
                else cls.convert_xml_type(value)
            )
            for key, value in elements.items()
        }

    @staticmethod
    def convert_xml_type(value: str | None) -> Any:
        """Convert string to Python type."""
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            match value.lower():
                case "true":
                    return True
                case "false":
                    return False
                case _:
                    return value
        raise ValueError("Unable to convert value")


class Registry:
    """Class to obtain and parse registry data."""

    WFS_PARTITION_MINOR = 255
    GROUP_GZ_FILENAME = "group.ini.gz"

    def __init__(self, data: str) -> None:
        """Initialise registry data."""
        self.text = data
        self.xml = self._get_valid_xml(self.text)
        self.root = ElementTree.fromstring(self.xml)

    @staticmethod
    def _get_valid_xml(data: str) -> str:
        """Transform registry data to valid XML."""
        data = re.sub(r"(\S*?)=<(.*?)>", r"<\1>\2</\1>", data, flags=re.DOTALL)
        data = re.sub(r"<(/?.*)%>", r"<\1>", data)
        data = "\n".join(["<root>", data.strip(), "</root>"])
        return data

    def get(self, key: str | Iterable[str]) -> str | None:
        """Get value from registry."""
        if isinstance(key, str):
            key = key.split(".")
        parent = self.root
        for part in key:
            if (child := parent.find(part)) is None:
                raise ValueError(f"Key '{part}' not found in registry")
            parent = child
        return parent.text

    def to_dict(self) -> RecursiveDict:
        """Return dictionary of registry data."""
        return XmlHelper.convert_xml_types(
            XmlHelper.convert_elements_to_strings(XmlHelper.to_dict(self.root))
        )

    @classmethod
    def from_filesystem(cls: type["Registry"], filesystem: Filesystem) -> "Registry":
        """Return Registry instance from filesystem."""
        if not _KEYRING_AVAILABLE:
            raise ImportError("Keyring functionality is not available")
        keyring = Keyring.from_filesystem(filesystem)
        key = keyring.get_key(cls.WFS_PARTITION_MINOR)
        data = Section.get_payload_of(
            filesystem.find_sections_by_directory(cls.WFS_PARTITION_MINOR),
            include_extents=False,
        )
        with tempfile_from_bytes(data) as wfs, tempfile_from_bytes(key) as keyfile:
            with Cryptsetup(wfs, keyfile) as mapping:
                with Mount(mapping) as mountpoint:
                    mountpoint = Path(mountpoint)
                    with open(mountpoint / cls.GROUP_GZ_FILENAME, "rb") as file:
                        data = file.read()
        data = gzip.decompress(data)
        return cls(data=data.decode())
