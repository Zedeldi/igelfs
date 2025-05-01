"""
Module to access IGEL filesystem image as a FUSE filesystem.

Based on https://github.com/libfuse/python-fuse/blob/master/example/hello.py
"""

import errno
import itertools
import os
import stat
from abc import ABC, abstractmethod
from collections.abc import Callable, Generator
from dataclasses import dataclass
from enum import StrEnum, auto
from functools import cached_property
from pathlib import Path
from typing import ClassVar

import fuse
from fuse import Fuse

from igelfs.device import get_parent_device
from igelfs.filesystem import Filesystem
from igelfs.models import Section
from igelfs.utils import get_size_of

if not hasattr(fuse, "__version__"):
    raise RuntimeError("fuse.__version__ is undefined")

fuse.fuse_python_api = (0, 2)


class Mode(StrEnum):
    """Enumeration for mode of FUSE operation."""

    PAYLOAD = auto()
    SECTION = auto()


@dataclass
class Entry(ABC):
    """Abstract dataclass for entries."""

    name: str

    @property
    @abstractmethod
    def data(self) -> bytes:
        """Return data for entry."""
        ...

    @property
    @abstractmethod
    def size(self) -> int:
        """Return size of data for entry."""
        ...


@dataclass
class PartitionDescriptor(Entry):
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


@dataclass
class PathDescriptor(Entry):
    """Dataclass to handle path information and methods."""

    name: str
    path: Path

    @property
    def data(self) -> bytes:
        """Return data as bytes from path."""
        with open(self.path, "rb") as file:
            return file.read()

    @cached_property
    def size(self) -> int:
        """Return size of data for partition."""
        return get_size_of(self.path)


class IgfFuse(Fuse):
    """Class to handle Filesystem as FUSE filesystem."""

    _FILE_MODE: ClassVar[int] = 0o444  # Read-only for all users
    ENTRY_PREFIX: ClassVar[str] = "igf"
    DEFAULT_MODE: ClassVar[Mode] = Mode.SECTION

    def __init__(self, *args, **kwargs) -> None:
        """Initialise instance."""
        super().__init__(*args, **kwargs)
        self.entry_prefix = self.ENTRY_PREFIX
        self.mode = self.DEFAULT_MODE

    def _get_partition_function(
        self, partition_minor: int, mode: Mode
    ) -> Callable[[], bytes]:
        """Return function to get data for partition from filesystem."""

        def inner() -> bytes:
            sections = self.filesystem.find_sections_by_directory(partition_minor)
            match mode:
                case Mode.SECTION:
                    return sections.to_bytes()
                case Mode.PAYLOAD:
                    return Section.get_payload_of(sections, include_extents=False)
                case _:
                    raise ValueError(f"Invalid mode '{mode}'")

        return inner

    @cached_property
    def _special_entries(self) -> tuple[Entry, ...]:
        """
        Return tuple of special entries.

        - boot: path to disk containing filesystem, e.g. sda
        - disk: path to filesystem, e.g. sda1
        - 0: synonym for disk/filesystem (as above), e.g. sda1
        - sys: system partition, e.g. igf1
        """
        return (
            PathDescriptor(
                name=f"{self.entry_prefix}boot",
                path=(
                    get_parent_device(path)
                    if (path := self.filesystem.path).is_block_device()
                    else path
                ),
            ),
            PathDescriptor(name=f"{self.entry_prefix}disk", path=self.filesystem.path),
            PathDescriptor(name=f"{self.entry_prefix}0", path=self.filesystem.path),
            PartitionDescriptor(
                name=f"{self.entry_prefix}sys",
                function=self._get_partition_function(1, mode=self.mode),
            ),
        )

    @cached_property
    def _partition_entries(self) -> tuple[Entry, ...]:
        """Return tuple of partition entries."""
        return tuple(
            PartitionDescriptor(
                name=f"{self.entry_prefix}{partition_minor}",
                function=self._get_partition_function(partition_minor, mode=self.mode),
            )
            for partition_minor in self.filesystem.partition_minors_by_directory
        )

    @cached_property
    def _entries(self) -> tuple[Entry, ...]:
        """Return tuple of all entries."""
        return self._special_entries + self._partition_entries

    @property
    def _entry_names(self) -> Generator[str]:
        """Return generator of entry names."""
        for entry in self._entries:
            yield entry.name

    def getattr(self, path: str) -> fuse.Stat:
        """Get attributes for path."""
        st = fuse.Stat()
        if path == "/":
            st.st_mode = stat.S_IFDIR | 0o755
            st.st_nlink = 1 + len(self._entries)
            return st
        for entry in self._entries:
            if path.removeprefix("/") == entry.name:
                st.st_mode = stat.S_IFREG | self._FILE_MODE
                st.st_nlink = 1
                st.st_size = entry.size
                return st
        return -errno.ENOENT

    def readdir(self, path: str, offset: int) -> Generator[fuse.Direntry]:
        """List directory entries."""
        for entry in itertools.chain((".", ".."), self._entry_names):
            yield fuse.Direntry(entry)

    def open(self, path: str, flags: int) -> int:
        """Open path and return flags."""
        if path.removeprefix("/") not in self._entry_names:
            return -errno.ENOENT
        accmode = os.O_RDONLY | os.O_WRONLY | os.O_RDWR
        if (flags & accmode) != os.O_RDONLY:
            return -errno.EACCES
        return 0

    def read(self, path: str, size: int, offset: int) -> bytes | int:
        """Read path and return bytes."""
        for entry in self._entries:
            if path.removeprefix("/") == entry.name:
                if offset >= entry.size:
                    # Offset is greater than size, return empty bytes
                    return b""
                if offset + size > entry.size:
                    # Read all data from offset to end
                    size = entry.size - offset
                return entry.data[offset : offset + size]
        # File does not exist
        return -errno.ENOENT

    def main(self, *args, **kwargs) -> None:
        """Parse additional arguments and call main Fuse method."""
        self.mode = Mode(self.mode)
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
    server.parser.add_option(
        mountopt="mode",
        metavar="MODE",
        default=server.DEFAULT_MODE,
        help=f"Mode for reading filesystem: {', '.join(Mode)} [default: %default]",
    )
    server.parser.add_option(
        mountopt="entry_prefix",
        metavar="PREFIX",
        default=server.ENTRY_PREFIX,
        help="Prefix for filesystem entries [default: %default]",
    )
    server.parse(values=server, errex=1)
    server.main()


if __name__ == "__main__":
    main()
