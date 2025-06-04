"""Module to handle WFS partition of the filesystem."""

import contextlib
from collections.abc import Generator
from pathlib import Path

from igelfs.device import Cryptsetup, Mount
from igelfs.filesystem import Filesystem
from igelfs.models import Section
from igelfs.utils import BaseContext, tempfile_from_bytes

try:
    from igelfs.kml import Keyring
except ImportError:
    _KEYRING_AVAILABLE = False
else:
    _KEYRING_AVAILABLE = True


class WfsPartition(BaseContext):
    """Class to handle WFS partition in a context manager."""

    WFS_PARTITION_MINOR = 255

    @classmethod
    @contextlib.contextmanager
    def context(cls: type["WfsPartition"], filesystem: Filesystem) -> Generator[Path]:
        """Context manager to mount WFS partition from filesystem, then unmount on closing."""
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
                    yield Path(mountpoint)
