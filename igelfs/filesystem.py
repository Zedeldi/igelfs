"""Python implementation to handle IGEL filesystems."""

import copy
import itertools
import logging
import math
import os
from collections.abc import Iterable, Iterator
from functools import cached_property
from pathlib import Path
from typing import Any, overload

from igelfs.constants import (
    DIR_OFFSET,
    DIR_SIZE,
    IGEL_BOOTREG_OFFSET,
    IGEL_BOOTREG_SIZE,
    IGF_SECTION_SIZE,
    SECTION_END_OF_CHAIN,
    PartitionType,
    SectionSize,
)
from igelfs.lxos import FirmwareUpdate, LXOSParser
from igelfs.models import (
    BootRegistryHeader,
    BootRegistryHeaderFactory,
    BootRegistryHeaderLegacy,
    DataModelCollection,
    Directory,
    Partition,
    PartitionHeader,
    Section,
    SectionHeader,
)
from igelfs.models.base import BaseDataModel
from igelfs.utils import (
    get_consecutive_values,
    get_section_of,
    get_size_of,
    get_start_of_section,
    guess_extension,
)

logger = logging.getLogger(__name__)


class Filesystem:
    """IGEL filesystem class to handle properties and methods."""

    def __init__(self, path: str | os.PathLike) -> None:
        """Initialise instance."""
        self.path = Path(path).resolve()

    @overload
    def __getitem__(self, index: int) -> Section:
        """Stub getitem method for indexes."""
        ...

    @overload
    def __getitem__(self, index: slice) -> DataModelCollection[Section]:
        """Stub getitem method for slices."""
        ...

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
        return get_size_of(self.path)

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
    def valid_sections(self) -> tuple[int, ...]:
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
        return self.directory.partition_minors

    @property
    def boot_registry(self) -> BootRegistryHeader | BootRegistryHeaderLegacy:
        """Return Boot Registry Header for image."""
        data = self.get_bytes(IGEL_BOOTREG_OFFSET, IGEL_BOOTREG_SIZE)
        return BootRegistryHeaderFactory.from_bytes(data)

    @property
    def directory(self) -> Directory:
        """Return Directory for image."""
        data = self.get_bytes(DIR_OFFSET, DIR_SIZE)
        return Directory.from_bytes(data)

    @classmethod
    def new(
        cls: type["Filesystem"], path: str | os.PathLike, size: int
    ) -> "Filesystem":
        """Create new IGEL filesystem at path of size in sections and return instance."""
        boot_registry = BootRegistryHeader.new()
        directory = Directory.new()
        directory.init_free_list()
        directory.update_free_list(first_section=1, length=size)
        # Directory does not fill rest of section #0
        # Pad out with null bytes
        directory_padding = bytes(DIR_SIZE - directory.get_actual_size())
        # Use generator to prevent consuming large amounts of RAM
        sections = (bytes(IGF_SECTION_SIZE) for _ in range(size))
        with open(path, "wb") as fd:
            for data in itertools.chain(
                (boot_registry, directory, directory_padding), sections
            ):
                if isinstance(data, bytes):
                    fd.write(data)
                elif isinstance(data, BaseDataModel):
                    fd.write(data.to_bytes())
                else:
                    raise TypeError(
                        f"Unexpected type '{type(data)}' found when creating filesystem"
                    )
        return cls(path)

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
        logger.debug(f"Writing {len(data)} bytes at {offset}")
        with open(self.path, "r+b") as fd:
            fd.seek(offset)
            return fd.write(data)

    def _write_model(self, model: BaseDataModel, offset: int) -> int:
        """Write data model to offset, returning number of written bytes."""
        logger.debug(f"Writing model {model.__class__.__name__} at {offset}")
        return self.write_bytes(model.to_bytes(), offset)

    def write_boot_registry(
        self, boot_registry: BootRegistryHeader | BootRegistryHeaderLegacy
    ) -> int:
        """Write boot registry to start (section #0) of image, returning number of written bytes."""
        if boot_registry.get_actual_size() != IGEL_BOOTREG_SIZE:
            raise ValueError(
                "Boot registry does not meet the expected size "
                f"({boot_registry.get_actual_size()} != {IGEL_BOOTREG_SIZE})"
            )
        return self._write_model(boot_registry, IGEL_BOOTREG_OFFSET)

    def write_directory(self, directory: Directory) -> int:
        """Write directory to start (section #0) of image, returning number of written bytes."""
        if directory.get_actual_size() != Directory.get_model_size():
            raise ValueError(
                "Directory does not meet the expected size "
                f"({directory.get_actual_size()} != {Directory.get_model_size()})"
            )
        return self._write_model(directory, DIR_OFFSET)

    def write_section_to_index(self, section: Section, index: int) -> int:
        """Write Section to index of image, returning number of written bytes."""
        if section.get_actual_size() != IGF_SECTION_SIZE:
            raise ValueError(
                "Section does not meet the expected size "
                f"({section.get_actual_size()} != {IGF_SECTION_SIZE})"
            )
        index = self._get_section_index(index)
        offset = get_start_of_section(index)
        logger.debug(f"Writing section to index {index}")
        return self._write_model(section, offset)

    def write_sections_at_index(
        self, sections: DataModelCollection[Section], index: int
    ) -> int:
        """
        Write collection of sections to image contiguously, starting at index.

        Return total number of written bytes.
        """
        return sum(
            self.write_section_to_index(section, index + offset)
            for offset, section in enumerate(sections)
        )

    def write_sections_to_unused(self, sections: DataModelCollection[Section]) -> int:
        """
        Write collection of sections to unused space, according to free list.

        Return first section of where data has been written.
        """
        directory = self.directory
        free_list = directory.free_list
        first_section = free_list.first_section
        if len(sections) > free_list.length:
            raise ValueError(
                f"Length of sections '{len(sections)}' is greater than free space '{free_list.length}'"
            )
        self.write_sections_at_index(sections, first_section)
        directory.update_free_list(
            first_section=first_section + len(sections),
            length=free_list.length - len(sections),
        )
        self.write_directory(directory)
        return first_section

    def write_partition(
        self, sections: DataModelCollection[Section], partition_minor: int
    ) -> None:
        """Write sections to unused space and create directory entry."""
        sections = copy.deepcopy(sections)
        if len(sections) > self.directory.free_list.length:
            self.update_free_list()
        first_section = self.directory.free_list.first_section
        for index, section in enumerate(sections):
            section.header.partition_minor = partition_minor
            # Cannot rely on section_in_minor due to upstream bug where
            # partition_minor was written to this field
            section.header.section_in_minor = index
            section.header.next_section = first_section + index + 1
        sections[-1].header.next_section = SECTION_END_OF_CHAIN
        for section in sections:
            section.update_crc()
        logger.info(f"Writing partition {partition_minor} ({len(sections)} sections)")
        self.write_sections_to_unused(sections)
        directory = self.directory
        directory.create_entry(partition_minor, first_section, len(sections))
        self.write_directory(directory)

    def delete_section_at_index(self, index: int) -> int:
        """
        Delete section at specified index by zeroing bytes.

        Return number of written bytes.
        """
        logger.debug(f"Deleting section at index {index}")
        data = bytes(IGF_SECTION_SIZE)
        index = self._get_section_index(index)
        offset = get_start_of_section(index)
        return self.write_bytes(data, offset)

    def delete_partition(self, partition_minor: int) -> None:
        """Delete partition and directory entry."""
        indexes = self.get_section_indexes_for_partition_minor(partition_minor)
        if not indexes:
            raise ValueError(f"Partition minor {partition_minor} not found")
        logger.info(f"Deleting partition {partition_minor}")
        for index in indexes:
            self.delete_section_at_index(index)
        directory = self.directory
        directory.delete_entry(partition_minor)
        self.write_directory(directory)

    def get_section_indexes_for_partition_minor(self, partition_minor: int) -> set[int]:
        """Return set of section indexes for partition minor."""
        fragment = self.directory.find_fragment_by_partition_minor(partition_minor)
        sections = self.find_sections_by_directory(partition_minor)
        if not fragment or not sections:
            return set()
        indexes = [fragment.first_section]
        indexes.extend(
            section.header.next_section
            for section in sections
            if not section.end_of_chain
        )
        return set(indexes)

    def get_used_section_indexes(self) -> set[int]:
        """Return set of used section indexes by directory."""
        indexes = set()
        for partition_minor in self.partition_minors_by_directory:
            indexes |= self.get_section_indexes_for_partition_minor(partition_minor)
        return indexes

    def get_unused_section_indexes(self) -> set[int]:
        """Return set of unused section indexes by directory."""
        # Exclude section #0 and remove used indexes from range
        return set(range(1, self.section_count + 1)) - self.get_used_section_indexes()

    def clean(self) -> None:
        """Zero any sections that are unused by directory."""
        for index in self.get_unused_section_indexes():
            self.delete_section_at_index(index)

    def update_free_list(self, largest: bool = True) -> None:
        """
        Update free list of directory to largest or next free section.

        If largest is True, set free list to use largest consecutive space.
        Otherwise, use the first available group.
        """
        indexes = get_consecutive_values(self.get_unused_section_indexes())
        if largest:
            group = max(indexes, key=len)
        else:
            group = indexes[0]
        first_section, length = group[0], len(group)
        logger.debug(
            f"Updating directory free list to first section {first_section} of length {length}"
        )
        directory = self.directory
        directory.update_free_list(first_section=first_section, length=length)
        self.write_directory(directory)

    def update(self, firmware: FirmwareUpdate) -> None:
        """Update filesystem partitions with firmware."""
        for partition_minor, data in firmware.get_partitions():
            logger.info(f"Updating partition {partition_minor} ({len(data)} bytes)")
            try:
                self.delete_partition(partition_minor)
            except ValueError:
                # Partition not found
                pass
            sections = Section.from_bytes_to_collection(data)
            self.write_partition(sections, partition_minor)

    @staticmethod
    def create_partition_from_bytes(
        data: bytes, type_: int | PartitionType = PartitionType.IGEL_RAW_RO
    ) -> DataModelCollection[Section]:
        """Create partition from bytes and return collection of sections."""
        size = math.ceil(len(data) / 1024)
        partition = Partition(
            PartitionHeader.new(
                type=type_,
                partlen=124 + size,
                n_blocks=size,
                n_clusters=math.ceil(size / (2**5)),
            )
        )
        payload = Section.split_into_sections(
            partition.to_bytes() + data,
            pad=True,
        )
        sections = DataModelCollection(
            Section.from_bytes(SectionHeader.new().to_bytes() + section)
            for section in payload
        )
        return sections

    @classmethod
    def create_partition_from_file(
        cls: type["Filesystem"], path: str | os.PathLike, *args, **kwargs
    ) -> DataModelCollection[Section]:
        """Create partition from file and return collection of sections."""
        with open(path, "rb") as fd:
            data = fd.read()
        return cls.create_partition_from_bytes(data, *args, **kwargs)

    def rebuild(self, path: str | os.PathLike) -> "Filesystem":
        """Rebuild filesystem to new image at path and return new instance."""
        filesystem = self.new(path, self.section_count - 1)
        filesystem.write_boot_registry(self.boot_registry)
        for partition_minor in sorted(self.partition_minors_by_directory):
            sections = self.find_sections_by_directory(partition_minor)
            filesystem.write_partition(sections, partition_minor)
        return filesystem

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

    def extract_to(
        self,
        path: str | os.PathLike,
        partition_minors: Iterable[int] | None = None,
        lxos_config: LXOSParser | None = None,
    ) -> None:
        """
        Extract all partitions and extents to path.

        Each partition will be extracted to its own directory, with partition
        extents extracted to a subdirectory.

        File extensions are guessed by MIME type.

        If lxos_config is specified, partition directories will be named accordingly.
        """
        path = Path(path).resolve()
        path.mkdir(exist_ok=True)
        for partition_minor in self.partition_minors_by_directory:
            if partition_minors and partition_minor not in partition_minors:
                continue
            sections = self.find_sections_by_directory(partition_minor)
            partition = sections[0].partition
            payload = Section.get_payload_of(sections)
            partition_name = (
                (
                    lxos_config
                    and lxos_config.find_name_by_partition_minor(partition_minor)
                )
                or (partition and partition.header.get_name())
                or f"{partition_minor}"
            )
            partition_path = path / partition_name
            payload_path = partition_path / f"payload{guess_extension(payload)}"
            logger.info(f"Extracting partition {partition_minor} to '{payload_path}'")
            self._extract_write(payload_path, payload)
            if partition and partition.extents:
                extents_path = partition_path / "extents"
                for index, extent in enumerate(partition.extents):
                    payload = Section.get_extent_of(sections, extent)
                    extent_name = f"{extent.get_name() or index}"
                    extent_path = (
                        extents_path / f"{extent_name}{guess_extension(payload)}"
                    )
                    logger.info(
                        f"Extracting partition extent '{extent_name}' of "
                        f"partition {partition_minor} to '{extent_path}'"
                    )
                    self._extract_write(extent_path, payload)

    @staticmethod
    def _extract_write(path: Path, data: bytes) -> int:
        """Write data to path and return number of written bytes."""
        path.parent.mkdir(exist_ok=True)
        with open(path, "wb") as fd:
            return fd.write(data)

    def get_info(self, lxos_config: LXOSParser | None = None) -> dict[str, Any]:
        """Return information about filesystem."""
        info: dict[str, Any] = {
            "path": self.path.as_posix(),
            "size": self.size,
            "section_count": self.section_count,
            "boot_registry": {
                "type": self.boot_registry.get_type(),
                "boot_id": self.boot_registry.get_boot_id(),
                "entries": self.boot_registry.get_entries(),
            },
            "partitions": {
                partition_minor: {}
                for partition_minor in sorted(self.partition_minors_by_directory)
            },
        }
        first_sections = self.directory.get_first_sections()
        for partition_minor, partition_info in info["partitions"].items():
            sections = self.find_sections_by_directory(partition_minor)
            partition_info.update(Section.get_info_of(sections))
            partition_info["first_section"] = first_sections.get(partition_minor)
            if lxos_config and not partition_info["name"]:
                partition_info["name"] = lxos_config.find_name_by_partition_minor(
                    partition_minor
                )
        return info
