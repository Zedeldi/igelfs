"""Data models for IGEL filesystem directory."""

from dataclasses import dataclass
from typing import ClassVar

from igelfs.constants import (
    DIR_MAX_MINORS,
    DIRECTORY_MAGIC,
    MAX_FRAGMENTS,
    PartitionType,
)
from igelfs.models.base import BaseDataModel
from igelfs.models.collections import DataModelCollection
from igelfs.models.mixins import CRCMixin


@dataclass
class FragmentDescriptor(BaseDataModel):
    """Dataclass to handle fragment descriptors."""

    MODEL_ATTRIBUTE_SIZES: ClassVar[dict[str, int]] = {"first_section": 4, "length": 4}

    first_section: int
    length: int  # number of sections


@dataclass
class PartitionDescriptor(BaseDataModel):
    """Dataclass to handle partition descriptors."""

    MODEL_ATTRIBUTE_SIZES: ClassVar[dict[str, int]] = {
        "minor": 4,
        "type": 2,
        "first_fragment": 2,
        "n_fragments": 2,
    }

    minor: int  # a replication of igf_sect_hdr.partition_minor
    type: int  # partition type, a replication of igf_part_hdr.type
    first_fragment: int  # index of the first fragment
    n_fragments: int  # number of additional fragments

    def get_type(self) -> PartitionType:
        """Return PartitionType from PartitionDescriptor instance."""
        return PartitionType(self.type)


@dataclass
class Directory(BaseDataModel, CRCMixin):
    """
    Dataclass to handle directory header data.

    The directory resides in section #0 of the image.
    """

    MODEL_ATTRIBUTE_SIZES: ClassVar[dict[str, int]] = {
        "magic": 4,
        "crc": 4,
        "dir_type": 2,
        "max_minors": 2,
        "version": 2,
        "dummy": 2,
        "n_fragments": 4,
        "max_fragments": 4,
        "extension": 8,
        "partition": DIR_MAX_MINORS * PartitionDescriptor.get_model_size(),
        "fragment": MAX_FRAGMENTS * FragmentDescriptor.get_model_size(),
    }
    DEFAULT_VALUES = {
        "magic": DIRECTORY_MAGIC,
        "version": 1,
        "max_minors": DIR_MAX_MINORS,
        "max_fragments": MAX_FRAGMENTS,
    }
    CRC_OFFSET = 4 + 4

    magic: str  # DIRECTORY_MAGIC
    crc: int
    dir_type: int  # allows for future extensions
    max_minors: int  # redundant, allows for dynamic part table
    version: int  # update count, never used so far
    dummy: int  # for future extensions
    n_fragments: int  # total number of fragments
    max_fragments: int  # redundant, allows for dynamic frag table
    extension: bytes  # unspecified, for future extensions
    partition: DataModelCollection[PartitionDescriptor]
    fragment: DataModelCollection[FragmentDescriptor]

    def __post_init__(self) -> None:
        """Verify magic string on initialisation."""
        if self.magic != DIRECTORY_MAGIC:
            raise ValueError(f"Unexpected magic '{self.magic}' for directory")

    @property
    def free_list(self) -> FragmentDescriptor:
        """Return fragment descriptor for free list."""
        return self.fragment[self.partition[0].first_fragment]

    @property
    def partition_minors(self) -> set[int]:
        """Return set of partition minors from directory."""
        partition_minors = {partition.minor for partition in self.partition}
        partition_minors.remove(0)  # Partition minor 0 does not exist
        return partition_minors

    def find_partition_by_partition_minor(
        self, partition_minor: int
    ) -> PartitionDescriptor | None:
        """Return PartitionDescriptor with matching partition minor."""
        for partition in self.partition:
            if partition.n_fragments == 0:
                continue  # partition does not exist
            if partition.minor == partition_minor:
                return partition
        return None

    def find_fragment_by_partition_minor(
        self, partition_minor: int
    ) -> FragmentDescriptor | None:
        """Return FragmentDescriptor from PartitionDescriptor with matching minor."""
        if not (partition := self.find_partition_by_partition_minor(partition_minor)):
            return None
        return self.fragment[partition.first_fragment]

    def get_first_sections(self) -> dict[int, int]:
        """Return mapping of partition minors to first sections."""
        info = {
            minor: self.find_fragment_by_partition_minor(minor).first_section
            for minor in sorted(self.partition_minors)
        }
        return info

    def _get_empty_partition(self) -> tuple[PartitionDescriptor, int]:
        """Get next available empty partition descriptor index and instance."""
        for index, partition in enumerate(self.partition):
            if partition.type == PartitionType.EMPTY:
                return (partition, index)
        else:
            raise ValueError("No empty partition descriptors found")

    def _get_empty_fragment(self) -> tuple[FragmentDescriptor, int]:
        """Get next available empty fragment descriptor index and instance."""
        for index, fragment in enumerate(self.fragment):
            if fragment.first_section == 0 and fragment.length == 0:
                return (fragment, index)
        else:
            raise ValueError("No empty fragment descriptors found")

    def create_entry(
        self, partition_minor: int, first_section: int, length: int
    ) -> None:
        """Create entry for specified data."""
        if self.find_fragment_by_partition_minor(partition_minor):
            raise ValueError(
                f"Fragment for partition minor #{partition_minor} already exists"
            )
        partition, _ = self._get_empty_partition()
        fragment, first_fragment = self._get_empty_fragment()
        partition.minor = partition_minor
        partition.type = PartitionType.IGEL_COMPRESSED
        partition.first_fragment = first_fragment
        partition.n_fragments = 1
        fragment.first_section = first_section
        fragment.length = length

    def update_entry(
        self, partition_minor: int, first_section: int, length: int
    ) -> None:
        """Update directory entry with specified data."""
        fragment = self.find_fragment_by_partition_minor(partition_minor)
        if not fragment:
            raise ValueError(
                f"Fragment for partition minor #{partition_minor} does not exist"
            )
        fragment.first_section = first_section
        fragment.length = length
