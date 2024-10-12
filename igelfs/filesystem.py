"""Python implementation to handle IGEL filesystems."""

import itertools
import os
from functools import cached_property
from pathlib import Path
from typing import Any, Iterator

from igelfs.constants import (
    DIR_OFFSET,
    DIR_SIZE,
    IGEL_BOOTREG_OFFSET,
    IGEL_BOOTREG_SIZE,
    IGF_SECTION_SIZE,
    SectionSize,
)
from igelfs.lxos import LXOSParser
from igelfs.models import (
    BootRegistryHeader,
    DataModelCollection,
    Directory,
    Partition,
    PartitionHeader,
    Section,
)
from igelfs.utils import get_section_of, get_start_of_section


class Filesystem:
    """IGEL filesystem class to handle properties and methods."""

    def __init__(self, path: str | Path) -> None:
        """Initialise instance."""
        self.path = Path(path).resolve()

    def __getitem__(self, index: int | slice) -> Section | DataModelCollection[Section]:
        """Implement getitem method."""
        if isinstance(index, slice):
            return DataModelCollection(
                section
                for section in itertools.islice(
                    self.sections, index.start, index.stop, index.step
                )
            )
        return self.get_section_by_index(index)

    def __iter__(self) -> Iterator[Section]:
        """Implement iter to make image iterable through sections."""
        yield from self.sections

    @property
    def size(self) -> int:
        """Return size of image."""
        if self.path.is_block_device():
            with open(self.path, "rb") as fd:
                return fd.seek(0, os.SEEK_END)
        return self.path.stat().st_size

    @property
    def section_size(self) -> SectionSize:
        """Return SectionSize for image."""
        return SectionSize.get(self.size)

    @property
    def section_count(self) -> int:
        """Return total number of sections of image."""
        return get_section_of(self.size)

    def get_valid_sections(self) -> Iterator[int]:
        """Return generator of valid section indices."""
        for index in range(self.section_count + 1):
            try:
                if self[index]:
                    yield index
            except ValueError:
                continue

    @cached_property
    def valid_sections(self) -> tuple[int]:
        """Return tuple of valid section indices and cache result."""
        return tuple(self.get_valid_sections())

    @property
    def sections(self) -> Iterator[Section]:
        """Return generator of sections."""
        for index in self.get_valid_sections():
            yield self[index]

    @property
    def partitions(self) -> Iterator[Partition]:
        """Return generator of partitions."""
        return (section.partition for section in self.sections if section.partition)

    @cached_property
    def partition_minors(self) -> set[int]:
        """Return set of partition minors."""
        return {section.header.partition_minor for section in self.sections}

    @property
    def partition_minors_by_directory(self) -> set[int]:
        """Return set of partition minors from directory."""
        partition_minors = {partition.minor for partition in self.directory.partition}
        partition_minors.remove(0)  # Partition minor 0 does not exist
        return partition_minors

    @property
    def boot_registry(self) -> BootRegistryHeader:
        """Return Boot Registry Header for image."""
        data = self.get_bytes(IGEL_BOOTREG_OFFSET, IGEL_BOOTREG_SIZE)
        return BootRegistryHeader.from_bytes(data)

    @property
    def directory(self) -> Directory:
        """Return Directory for image."""
        data = self.get_bytes(DIR_OFFSET, DIR_SIZE)
        return Directory.from_bytes(data)

    def get_bytes(self, offset: int = 0, size: int = -1) -> bytes:
        """Return bytes for specified offset and size."""
        if offset > self.size:
            raise ValueError("Offset is greater than image size")
        with open(self.path, "rb") as fd:
            fd.seek(offset)
            return fd.read(size)

    def write_bytes(self, data: bytes, offset: int = 0) -> int:
        """Write bytes to specified offset, returning number of written bytes."""
        if offset > self.size:
            raise ValueError("Offset is greater than image size")
        with open(self.path, "r+b") as fd:
            fd.seek(offset)
            return fd.write(data)

    def get_section_by_offset(self, offset: int, size: int) -> Section:
        """Return Section of image by offset and size."""
        data = self.get_bytes(offset, size)
        return Section.from_bytes(data)

    def _get_section_index(self, index: int) -> int:
        """Return real section index from integer."""
        if index > self.section_count:
            raise IndexError("Index is greater than section count")
        if index < 0:
            # Implement indexing from end, e.g. -1 = last element
            return self.section_count - abs(index + 1)
        return index

    def get_section_by_index(self, index: int) -> Section:
        """Return Section of image by index."""
        index = self._get_section_index(index)
        offset = get_start_of_section(index)
        data = self.get_bytes(offset, IGF_SECTION_SIZE)
        return Section.from_bytes(data)

    def write_section_to_index(self, section: Section, index: int) -> int:
        """Write Section to index of image, returning number of written bytes."""
        if section.get_actual_size() != IGF_SECTION_SIZE:
            raise ValueError(
                "Section does not meet the expected size "
                f"({section.get_actual_size()} != {IGF_SECTION_SIZE})"
            )
        index = self._get_section_index(index)
        offset = get_start_of_section(index)
        return self.write_bytes(section.to_bytes(), offset)

    def find_sections_by_partition_minor(
        self, partition_minor: int
    ) -> DataModelCollection[Section]:
        """Return Sections with matching partition minor by searching linearly."""
        return DataModelCollection(
            section
            for section in self.sections
            if section.header.partition_minor == partition_minor
        )

    def find_sections_by_directory(
        self, partition_minor: int
    ) -> DataModelCollection[Section]:
        """Return Sections with matching partition minor from directory."""
        fragment = self.directory.find_fragment_by_partition_minor(partition_minor)
        if not fragment:
            return DataModelCollection()
        sections = DataModelCollection([self[fragment.first_section]])
        while not (section := sections[-1]).end_of_chain:
            sections.append(self[section.header.next_section])
        if not len(sections) == fragment.length:
            raise ValueError(
                f"Total count of sections '{len(sections)}' "
                f"did not match fragment length '{fragment.length}'"
            )
        return sections

    def find_section_by_partition_header(
        self, partition_header: PartitionHeader
    ) -> Section | None:
        """Return Section with matching PartitionHeader by searching linearly."""
        for section in self.sections:
            if section.partition and section.partition.header == partition_header:
                return section
        return None

    def find_partition_by_hash(self, hash_: bytes | str) -> Partition | None:
        """Return Partition for specified hash by searching linearly."""
        if isinstance(hash_, str):
            hash_ = bytes.fromhex(hash_)
        for partition in self.partitions:
            if partition.header.update_hash == hash_:
                return partition
        return None

    def get_info(self, lxos_config: LXOSParser | None = None) -> dict[str, Any]:
        """Return information about filesystem."""
        info = {
            "path": self.path.as_posix(),
            "size": self.size,
            "section_count": self.section_count,
            "partition_minors": sorted(self.partition_minors),
        }
        if lxos_config:
            info["partition_names"] = [
                lxos_config.find_name_by_partition_minor(partition_minor)
                for partition_minor in info["partition_minors"]
            ]
        return info
