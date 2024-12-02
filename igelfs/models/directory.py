"""Data models for IGEL filesystem directory."""

from dataclasses import dataclass
from typing import ClassVar

from igelfs.constants import DIR_MAX_MINORS, DIRECTORY_MAGIC, MAX_FRAGMENTS
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
    DEFAULT_VALUES = {"magic": DIRECTORY_MAGIC}
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
