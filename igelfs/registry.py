"""Module to access and parse IGEL OS registry."""

import gzip
import re
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


class Registry:
    """Class to obtain and parse registry data."""

    WFS_PARTITION_MINOR = 255
    GROUP_GZ_FILENAME = "group.ini.gz"

    def __init__(self, group: str) -> None:
        """Initialise registry data."""
        self.root = ElementTree.fromstring(group)

    @staticmethod
    def _get_valid_xml(data: str) -> str:
        """Transform data to valid XML."""
        data = re.sub(r"=<(.*?)>", r"=\1", data, flags=re.DOTALL)
        data = re.sub(r"<(/?.*)%>", r"<\1>", data)
        data = "\n".join(["<root>", data.strip(), "</root>"])
        return data

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
        group = gzip.decompress(data).decode()
        group = cls._get_valid_xml(group)
        return cls(group=group)
