"""Data models for IGEL filesystem directory."""

from dataclasses import dataclass, field

from igelfs.constants import (
    DIR_MAX_MINORS,
    DIRECTORY_MAGIC,
    MAX_FRAGMENTS,
    PartitionType,
)
from igelfs.models.base import BaseDataModel, DataModelMetadata
from igelfs.models.collections import DataModelCollection
from igelfs.models.mixins import CRCMixin


@dataclass
class FragmentDescriptor(BaseDataModel):
    """Dataclass to handle fragment descriptors."""

    first_section: int = field(metadata=DataModelMetadata(size=4))
    length: int = field(metadata=DataModelMetadata(size=4))  # number of sections


@dataclass
class PartitionDescriptor(BaseDataModel):
    """Dataclass to handle partition descriptors."""

    minor: int = field(  # partition minor, copy of SectionHeader.partition_minor
        metadata=DataModelMetadata(size=4)
    )
    type: int = field(  # partition type, copy of PartitionHeader.type
        metadata=DataModelMetadata(size=2)
    )
    first_fragment: int = field(  # index of the first fragment
        metadata=DataModelMetadata(size=2)
    )
    n_fragments: int = field(  # number of additional fragments
        metadata=DataModelMetadata(size=2)
    )

    def get_type(self) -> PartitionType:
        """Return PartitionType from PartitionDescriptor instance."""
        return PartitionType(self.type)


@dataclass
class Directory(BaseDataModel, CRCMixin):
    """
    Dataclass to handle directory header data.

    The directory resides in section #0 of the image.
    """

    CRC_OFFSET = 4 + 4

    # DIRECTORY_MAGIC
    magic: str = field(metadata=DataModelMetadata(size=4, default=DIRECTORY_MAGIC))
    crc: int = field(metadata=DataModelMetadata(size=4))
    dir_type: int = field(  # allows for future extensions
        metadata=DataModelMetadata(size=2)
    )
    max_minors: int = field(  # redundant, allows for dynamic partition table
        metadata=DataModelMetadata(size=2, default=DIR_MAX_MINORS)
    )
    version: int = field(  # update count, never used so far
        metadata=DataModelMetadata(size=2, default=1)
    )
    dummy: int = field(metadata=DataModelMetadata(size=2))  # for future extensions
    n_fragments: int = field(  # total number of fragments
        metadata=DataModelMetadata(size=4)
    )
    max_fragments: int = field(  # redundant, allows for dynamic fragment table
        metadata=DataModelMetadata(size=4, default=MAX_FRAGMENTS)
    )
    extension: bytes = field(  # unspecified, for future extensions
        metadata=DataModelMetadata(size=8)
    )
    partition: DataModelCollection[PartitionDescriptor] = field(
        metadata=DataModelMetadata(
            size=DIR_MAX_MINORS * PartitionDescriptor.get_model_size()
        )
    )
    fragment: DataModelCollection[FragmentDescriptor] = field(
        metadata=DataModelMetadata(
            size=MAX_FRAGMENTS * FragmentDescriptor.get_model_size()
        )
    )

    def __post_init__(self) -> None:
        """Verify magic string on initialisation."""
        if self.magic != DIRECTORY_MAGIC:
            raise ValueError(f"Unexpected magic '{self.magic}' for directory")

    @property
    def free_list(self) -> FragmentDescriptor:
        """Return fragment descriptor for free list."""
        partition = self.find_partition_by_partition_type(PartitionType.IGEL_FREELIST)
        if not partition:
            raise ValueError("Free list not found")
        return self.fragment[partition.first_fragment]

    def init_free_list(self) -> None:
        """Initialise free list of directory."""
        partition = self.partition[0]
        partition.minor = 0
        partition.type = PartitionType.IGEL_FREELIST
        partition.first_fragment = 0
        partition.n_fragments = 1

    def update_free_list(self, first_section: int, length: int) -> None:
        """Update free list with specified data."""
        self.free_list.first_section = first_section
        self.free_list.length = length

    @property
    def partition_minors(self) -> set[int]:
        """Return set of partition minors from directory."""
        partition_minors = {partition.minor for partition in self.partition}
        partition_minors.remove(0)  # Partition minor 0 does not exist
        return partition_minors

    def find_partition_by_partition_type(
        self, partition_type: PartitionType
    ) -> PartitionDescriptor | None:
        """Return PartitionDescriptor with matching partition type."""
        for partition in self.partition:
            if partition.type == partition_type:
                return partition
        return None

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
        info = {}
        for minor in sorted(self.partition_minors):
            fragment = self.find_fragment_by_partition_minor(minor)
            if not fragment:
                continue
            info[minor] = fragment.first_section
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

    def _get_n_fragments(self) -> int:
        """Return number of fragments in directory."""
        return len(
            [
                fragment
                for fragment in self.fragment
                if fragment.first_section and fragment.length
            ]
        )

    def create_entry(
        self, partition_minor: int, first_section: int, length: int
    ) -> None:
        """Create entry for specified data."""
        if self.find_fragment_by_partition_minor(partition_minor):
            raise ValueError(
                f"Fragment for partition minor #{partition_minor} already exists"
            )
        # Partition descriptors are stored at index of partition_minor
        partition = self.partition[partition_minor]
        fragment, first_fragment = self._get_empty_fragment()
        partition.minor = partition_minor
        partition.type = PartitionType.IGEL_COMPRESSED
        partition.first_fragment = first_fragment
        partition.n_fragments = 1
        fragment.first_section = first_section
        fragment.length = length
        self.n_fragments = self._get_n_fragments()
        self.update_crc()

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
        self.update_crc()

    def delete_entry(self, partition_minor: int) -> None:
        """Delete directory entry for specified partition minor."""
        fragment = self.find_fragment_by_partition_minor(partition_minor)
        if not fragment:
            raise ValueError(
                f"Fragment for partition minor #{partition_minor} does not exist"
            )
        fragment_index = self.partition[partition_minor].first_fragment
        self.partition[partition_minor] = PartitionDescriptor.new()
        self.fragment[fragment_index] = FragmentDescriptor.new()
        self.update_crc()
