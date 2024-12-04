"""Data models for a partition."""

from dataclasses import dataclass, field

from igelfs.constants import MAX_EXTENT_NUM, ExtentType, PartitionType
from igelfs.models.base import BaseDataGroup, BaseDataModel, DataModelMetadata
from igelfs.models.collections import DataModelCollection


@dataclass
class PartitionHeader(BaseDataModel):
    """
    Dataclass to handle partition header data.

    Contains the partition and header size, update hash and name for directory.
    n_blocks / (2 ** cluster_shift) == n_clusters
    hdrlen + <length of extents payload> + (n_blocks * 1024) == partlen
    offset_blocktable == offset_blocks == start of actual payload (after extents)
    """

    type: int = field(metadata=DataModelMetadata(size=2))  # partition type
    hdrlen: int = field(  # length of the complete partition header (incl. extents)
        metadata=DataModelMetadata(size=2, default=124)
    )
    partlen: int = field(  # length of this partition (incl. header)
        metadata=DataModelMetadata(size=8)
    )
    n_blocks: int = field(  # number of uncompressed 1k blocks
        metadata=DataModelMetadata(size=8)
    )
    offset_blocktable: int = field(  # needed for compressed partitions
        metadata=DataModelMetadata(size=8, default=124)
    )
    offset_blocks: int = field(  # start of the compressed block clusters
        metadata=DataModelMetadata(size=8, default=124)
    )
    n_clusters: int = field(metadata=DataModelMetadata(size=4))  # number of clusters
    cluster_shift: int = field(  # 2^x blocks make up a cluster
        metadata=DataModelMetadata(size=2, default=5)
    )
    n_extents: int = field(  # number of extents, if any
        metadata=DataModelMetadata(size=2)
    )
    name: bytes = field(  # optional character code (for pdir)
        metadata=DataModelMetadata(size=16)
    )
    # A high level hash over almost all files, used to determine if an update is needed
    update_hash: bytes = field(metadata=DataModelMetadata(size=64))

    def __post_init__(self) -> None:
        """Handle model-specific data post-initialisation."""
        size = self.get_model_size() + (
            self.n_extents * PartitionExtent.get_model_size()
        )
        if self.hdrlen != size:
            raise ValueError(
                f"Size '{size}' does not match hdrlen '{self.hdrlen}' for partition header"
            )

    def get_type(self) -> PartitionType:
        """Return PartitionType from PartitionHeader instance."""
        type_ = int.from_bytes(
            self.type.to_bytes(self.get_attribute_size("type"), byteorder="big"),
            byteorder="little",
        )
        return PartitionType(type_ & 0xFF)

    def get_name(self) -> str | None:
        """Return name of partition or None."""
        return self.name.rstrip(b"\x00").decode() or None


@dataclass
class PartitionExtent(BaseDataModel):
    """Dataclass to handle partition extent data."""

    type: int = field(  # type of extent -> ExtentType
        metadata=DataModelMetadata(size=2)
    )
    offset: int = field(  # offset from start of partition header
        metadata=DataModelMetadata(size=8)
    )
    length: int = field(metadata=DataModelMetadata(size=8))  # size of data in bytes
    name: bytes = field(metadata=DataModelMetadata(size=8))  # optional character code

    def get_type(self) -> ExtentType:
        """Return ExtentType from PartitionExtent instance."""
        return ExtentType(self.type)

    def get_name(self) -> str:
        """Return name of PartitionExtent instance as a string."""
        return self.name.strip(b"\x00").decode()


@dataclass
class PartitionExtents(BaseDataModel):
    """Dataclass to handle partition extents."""

    n_extents: int = field(metadata=DataModelMetadata(size=2))
    extent: DataModelCollection[PartitionExtent] = field(
        metadata=DataModelMetadata(
            size=MAX_EXTENT_NUM * PartitionExtent.get_model_size()
        )
    )


@dataclass
class PartitionExtentReadWrite(BaseDataModel):
    """Dataclass to handle partition extent read/write data."""

    ext_num: int = field(  # extent number where to read from
        metadata=DataModelMetadata(size=1)
    )
    pos: int = field(  # position inside extent to start reading from
        metadata=DataModelMetadata(size=8)
    )
    size: int = field(  # size of data (WARNING limited to EXTENT_MAX_READ_WRITE_SIZE)
        metadata=DataModelMetadata(size=8)
    )
    data: int = field(  # destination/src pointer for the data to
        metadata=DataModelMetadata(size=1)
    )


@dataclass
class Partition(BaseDataGroup):
    """Dataclass to store and handle partition-related data models."""

    header: PartitionHeader
    extents: DataModelCollection[PartitionExtent] = field(
        default_factory=DataModelCollection
    )

    def get_extents_length(self) -> int:
        """Return length of all extents in bytes."""
        return sum(extent.length for extent in self.extents)
