"""
Module to access IGEL filesystem image as a FUSE filesystem.

Based on https://github.com/libfuse/python-fuse/blob/master/example/hello.py
"""

import errno
import itertools
import os
import stat
from collections.abc import Callable, Generator
from dataclasses import dataclass
from functools import cached_property
from typing import ClassVar

import fuse
from fuse import Fuse

from igelfs.filesystem import Filesystem

if not hasattr(fuse, "__version__"):
    raise RuntimeError("fuse.__version__ is undefined")

fuse.fuse_python_api = (0, 2)


@dataclass
class PartitionDescriptor:
    """Dataclass to store partition information and methods."""

    name: str
    # Function to get partition data, to prevent using large amounts of memory
    function: Callable[[], bytes]

    @property
    def data(self) -> bytes:
        """Wrap function to return bytes for partition as property."""
        return self.function()

    @cached_property
    def size(self) -> int:
        """Return size of data for partition."""
        return len(self.data)


class IgfFuse(Fuse):
    """Class to handle Filesystem as FUSE filesystem."""

    _DIRENTRY_PREFIX: ClassVar[str] = "igf"
    _FILE_MODE: ClassVar[int] = 0o444  # Read-only for all users

    def _get_partition_function(self, partition_minor: int) -> Callable[[], bytes]:
        """Return function to get data for partition from filesystem."""

        def inner() -> bytes:
            return self.filesystem.find_sections_by_directory(
                partition_minor
            ).to_bytes()

        return inner

    @cached_property
    def _partition_entries(self) -> tuple[PartitionDescriptor, ...]:
        """Return tuple of partition entries."""
        return tuple(
            PartitionDescriptor(
                name=f"{self._DIRENTRY_PREFIX}{partition_minor}",
                function=self._get_partition_function(partition_minor),
            )
            for partition_minor in self.filesystem.partition_minors_by_directory
        )

    @property
    def _partition_names(self) -> Generator[str]:
        """Return tuple of partition names."""
        for partition in self._partition_entries:
            yield partition.name

    def getattr(self, path: str) -> fuse.Stat:
        """Get attributes for path."""
        st = fuse.Stat()
        if path == "/":
            st.st_mode = stat.S_IFDIR | 0o755
            st.st_nlink = 1 + len(self._partition_entries)
            return st
        for partition in self._partition_entries:
            if path.removeprefix("/") == partition.name:
                st.st_mode = stat.S_IFREG | self._FILE_MODE
                st.st_nlink = 1
                st.st_size = partition.size
                return st
        return -errno.ENOENT

    def readdir(self, path: str, offset: int) -> Generator[fuse.Direntry]:
        """List directory entries."""
        for entry in itertools.chain(
            (".", ".."),
            (partition.name for partition in self._partition_entries),
        ):
            yield fuse.Direntry(entry)

    def open(self, path: str, flags: int) -> int:
        """Open path and return flags."""
        if path.removeprefix("/") not in self._partition_names:
            return -errno.ENOENT
        accmode = os.O_RDONLY | os.O_WRONLY | os.O_RDWR
        if (flags & accmode) != os.O_RDONLY:
            return -errno.EACCES
        return 0

    def read(self, path: str, size: int, offset: int) -> bytes | int:
        """Read path and return bytes."""
        for partition in self._partition_entries:
            if path.removeprefix("/") == partition.name:
                if offset >= partition.size:
                    # Offset is greater than size, return empty bytes
                    return b""
                if offset + size > partition.size:
                    # Read all data from offset to end
                    size = partition.size - offset
                return partition.data[offset : offset + size]
        # File does not exist
        return -errno.ENOENT

    def main(self, *args, **kwargs) -> None:
        """Parse additional arguments and call main Fuse method."""
        try:
            self.filesystem = Filesystem(self.cmdline[1][0])
        except IndexError:
            raise ValueError("Missing underlying filesystem path parameter") from None
        return Fuse.main(self, *args, **kwargs)


def main():
    """Create Fuse server, parse arguments and invoke main method."""
    server = IgfFuse(
        version=f"%prog {fuse.__version__}", usage=Fuse.fusage, dash_s_do="setsingle"
    )
    server.parse(errex=1)
    server.main()


if __name__ == "__main__":
    main()
