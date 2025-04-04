"""Module to access and parse IGEL OS registry."""

import gzip
import re
from collections.abc import Iterable
from pathlib import Path
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

type Primitive = int | float | str | bool | None
type RecursiveDict[K, V] = dict[K, RecursiveDict[K, V] | V]
type ElementText = str | None
type ElementDict = RecursiveDict[ElementTree.Element, ElementDict | ElementText]


class XmlHelper:
    """Helper class for generic XML methods."""

    @classmethod
    def to_dict(cls: type["XmlHelper"], element: ElementTree.Element) -> ElementDict:
        """Return dictionary of children for element."""
        return {
            child: (
                children
                if (children := cls.to_dict(child))
                else (text.strip() if (text := child.text) else text)
            )
            for child in element
        }

    @classmethod
    def keys(
        cls: type["XmlHelper"],
        element: ElementTree.Element,
        separator: str = ".",
        prefix: list[str] | None = None,
    ) -> list[str]:
        """Return flat list of keys separated by separator."""
        prefix = prefix or []
        data = cls.to_dict(element)
        keys = []
        for element, value in data.items():
            if isinstance(value, dict):
                keys.extend(
                    cls.keys(
                        element, separator=separator, prefix=[*prefix, element.tag]
                    )
                )
            else:
                keys.append(separator.join([*prefix, element.tag]))
        return keys

    @classmethod
    def convert_elements_to_strings(
        cls: type["XmlHelper"], elements: ElementDict
    ) -> RecursiveDict[str, ElementText]:
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
        cls: type["XmlHelper"], elements: RecursiveDict[str, ElementText]
    ) -> RecursiveDict[str, Primitive]:
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
    def convert_xml_type(value: str | None) -> Primitive:
        """Convert string to Python type."""
        if not value:  # includes empty string
            return None
        for type_ in (int, float):
            try:
                return type_(value)
            except ValueError:
                pass
        match value.lower():
            case "true":
                return True
            case "false":
                return False
            case _:
                return value
        raise ValueError("Unable to convert value")


class Registry:
    """
    Class to obtain and parse registry data.

    Registry data is found in group.ini and setup.ini of partition minor 255 (wfs).
    These files, despite their file extension, are partially XML-formatted, with
    key-values separated by equals signs.

    For example:
    <x>
      <xserver0>
        resolution=<1360x768>
      </xserver0>
    </x>

    This data will be transformed into valid XML using regex, then parsed.

    Sensitive values, such as passwords, are 'encrypted' using a simple
    XOR-based algorithm (see Registry.encrypt and Registry.decrypt).
    """

    WFS_PARTITION_MINOR = 255
    GROUP_FILENAME = "group.ini"
    GROUP_GZ_FILENAME = "group.ini.gz"
    KEY_SEPARATOR = "."
    DEFAULT_PASSWORD = 0x43

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

    def get(
        self, key: str | Iterable[str], separator: str = KEY_SEPARATOR
    ) -> Primitive:
        """Get value from registry."""
        if isinstance(key, str):
            key = key.split(separator)
        parent = self.root
        for part in key:
            if (child := parent.find(part)) is None:
                raise ValueError(f"Key '{part}' not found in registry")
            parent = child
        return XmlHelper.convert_xml_type(parent.text)

    def get_crypt(self, key: str | Iterable[str]) -> str:
        """Get and decrypt value from registry."""
        value = self.get(key)
        if not isinstance(value, str):
            raise TypeError("Cannot decrypt non-string value")
        return self.decrypt(value)

    def keys(self, separator: str = KEY_SEPARATOR) -> list[str]:
        """Return flat list of registry keys separated by separator."""
        return XmlHelper.keys(self.root, separator=separator)

    def to_dict(self) -> RecursiveDict[str, Primitive]:
        """Return dictionary of registry data."""
        return XmlHelper.convert_xml_types(
            XmlHelper.convert_elements_to_strings(XmlHelper.to_dict(self.root))
        )

    @staticmethod
    def encrypt(plaintext: str, password: int = DEFAULT_PASSWORD) -> str:
        """Encrypt plaintext for registry and return result."""
        prefix = hex(len(plaintext) + 1)[2:].zfill(4) + hex(password)[2:]
        ciphertext = []
        result = 0
        for char in plaintext:
            result = ord(char) ^ result ^ password
            enc_char = hex(result)[2:]
            ciphertext.append(enc_char.zfill(2))
        return prefix + "".join(ciphertext)

    @staticmethod
    def decrypt(ciphertext: str, strict: bool = True) -> str:
        """
        Decrypt ciphertext from registry and return result.

        ciphertext is a hexadecimal string, containing the length (2 bytes),
        password (1 byte) and payload (remaining bytes).
        Each byte is XORed with the previous result (initially 0) and the password.

        As the password is stored with the ciphertext, this only provides
        security through obscurity.
        """
        length, password, data = (
            int(ciphertext[:4], 16) - 1,
            int(ciphertext[4:6], 16),
            ciphertext[6:],
        )
        plaintext = []
        prev_chunk = 0
        for idx in range(0, len(data), 2):
            chunk = int(data[idx : idx + 2], 16)
            result = chunk ^ prev_chunk ^ password
            plaintext.append(chr(result))
            prev_chunk = chunk
        if strict and length != len(plaintext):
            raise ValueError(
                f"Length '{length}' does not equal length of data '{len(plaintext)}'"
            )
        return "".join(plaintext)

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
                    if (path := (mountpoint / cls.GROUP_FILENAME)).exists():
                        with open(path, "rb") as file:
                            data = file.read()
                    else:
                        with open(mountpoint / cls.GROUP_GZ_FILENAME, "rb") as file:
                            data = gzip.decompress(file.read())
        return cls(data=data.decode())
