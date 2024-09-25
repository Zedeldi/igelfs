"""Python implementation to handle IGEL filesystems."""

import itertools
from pathlib import Path
from typing import Iterator

from igelfs.constants import (
    DIR_OFFSET,
    DIR_SIZE,
    IGEL_BOOTREG_OFFSET,
    IGEL_BOOTREG_SIZE,
    IGF_SECTION_SIZE,
    SectionSize,
    get_section_of,
    get_start_of_section,
)
from igelfs.models import BootRegistryHeader, Directory, PartitionHeader, Section


class Filesystem:
    """IGEL filesystem class to handle properties and methods."""

    def __init__(self, path: str | Path) -> None:
        """Initialise instance."""
        self.path = Path(path).absolute()

    def __getitem__(self, index: int | slice) -> Section | list[Section]:
        """Implement getitem method."""
        if isinstance(index, slice):
            return [
                section
                for section in itertools.islice(
                    self.sections, index.start, index.stop, index.step
                )
            ]
        return self.get_section_by_index(index)

    def __iter__(self) -> Iterator[Section]:
        """Implement iter to make image iterable through sections."""
        yield from self.sections

    @property
    def size(self) -> int:
        """Return size of image."""
        return self.path.stat().st_size

    @property
    def section_size(self) -> SectionSize:
        """Return SectionSize for image."""
        return SectionSize.get(self.size)

    @property
    def section_count(self) -> int:
        """Return total number of sections of image."""
        return get_section_of(self.size)

    @property
    def sections(self) -> Iterator[Section]:
        """Return generator of sections."""
        return (self[index] for index in range(self.section_count + 1))

    @property
    def partitions(self) -> Iterator[PartitionHeader]:
        """Return generator of partition headers."""
        return (section.partition for section in self.sections if section.partition)

    @property
    def bootreg(self) -> BootRegistryHeader:
        """Return Boot Registry Header for image."""
        data = self.get_data(IGEL_BOOTREG_OFFSET, IGEL_BOOTREG_SIZE)
        return BootRegistryHeader.from_bytes(data)

    @property
    def directory(self) -> Directory:
        """Return Directory for image."""
        data = self.get_data(DIR_OFFSET, DIR_SIZE)
        return Directory.from_bytes(data)

    def get_data(self, offset: int = 0, size: int = -1):
        """Return data for specified offset and size."""
        if offset > self.size:
            raise ValueError("Offset is greater than image size")
        with open(self.path, "rb") as fd:
            fd.seek(offset)
            return fd.read(size)

    def get_section_by_offset(self, offset: int, size: int) -> Section:
        """Return Section of image by offset and size."""
        data = self.get_data(offset, size)
        return Section.from_bytes(data)

    def get_section_by_index(self, index: int) -> Section:
        """Return Section of image by index."""
        if index > self.section_count:
            raise IndexError("Index is greater than section count")
        offset = get_start_of_section(index)
        data = self.get_data(offset, IGF_SECTION_SIZE)
        return Section.from_bytes(data)

    def get_partition_by_hash(self, hash: bytes | str) -> PartitionHeader | None:
        """Return PartitionHeader for specified hash."""
        if isinstance(hash, str):
            hash = bytes.fromhex(hash)
        try:
            return [partition for partition in self.partitions if partition.update_hash == hash][0]
        except IndexError:
            return None