"""Data models for a partition."""

from dataclasses import dataclass, field
from typing import ClassVar

from igelfs.constants import MAX_EXTENT_NUM, ExtentType, PartitionType
from igelfs.models.base import BaseDataModel
from igelfs.models.collections import DataModelCollection


@dataclass
class PartitionHeader(BaseDataModel):
    """
    Dataclass to handle partition header data.

    Contains the partition and header size, update hash and name for directory.
    n_blocks / (2 ** cluster_shift) == n_clusters
    """

    MODEL_ATTRIBUTE_SIZES: ClassVar[dict[str, int]] = {
        "type": 2,
        "hdrlen": 2,
        "partlen": 8,
        "n_blocks": 8,
        "offset_blocktable": 8,
        "offset_blocks": 8,
        "n_clusters": 4,
        "cluster_shift": 2,
        "n_extents": 2,
        "name": 16,
        "update_hash": 64,
    }

    type: int  # partition type
    hdrlen: int  # length of the complete partition header (incl. extents)
    partlen: int  # length of this partition (incl. header)
    n_blocks: int  # number of uncompressed 1k blocks
    offset_blocktable: int  # needed for compressed partitions
    offset_blocks: int  # start of the compressed block clusters
    n_clusters: int  # number of clusters
    cluster_shift: int  # 2^x blocks make up a cluster
    n_extents: int  # number of extents, if any
    name: bytes  # optional character code (for pdir)
    # A high level hash over almost all files, used to determine if an update is needed
    update_hash: bytes

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
            self.type.to_bytes(self.MODEL_ATTRIBUTE_SIZES["type"], byteorder="big"),
            byteorder="little",
        )
        return PartitionType(type_ & 0xFF)


@dataclass
class PartitionExtent(BaseDataModel):
    """Dataclass to handle partition extent data."""

    MODEL_ATTRIBUTE_SIZES: ClassVar[dict[str, int]] = {
        "type": 2,
        "offset": 8,
        "length": 8,
        "name": 8,
    }

    type: int
    offset: int
    length: int
    name: bytes  # optional character code

    def get_type(self) -> ExtentType:
        """Return ExtentType from PartitionExtent instance."""
        return ExtentType(self.type)


@dataclass
class PartitionExtents(BaseDataModel):
    """Dataclass to handle partition extents."""

    MODEL_ATTRIBUTE_SIZES: ClassVar[dict[str, int]] = {
        "n_extents": 2,
        "extent": MAX_EXTENT_NUM * PartitionExtent.get_model_size(),
    }

    n_extents: int
    extent: DataModelCollection[PartitionExtent]


@dataclass
class PartitionExtentReadWrite(BaseDataModel):
    """Dataclass to handle partition extent read/write data."""

    MODEL_ATTRIBUTE_SIZES: ClassVar[dict[str, int]] = {
        "ext_num": 1,
        "pos": 8,
        "size": 8,
        "data": 1,
    }

    ext_num: int  # extent number where to read from
    pos: int  # position inside extent to start reading from
    size: int  # size of data (WARNING limited to EXTENT_MAX_READ_WRITE_SIZE)
    data: int  # destination/src pointer for the data to


@dataclass
class Partition:
    """Dataclass to store and handle partition-related data models."""

    header: PartitionHeader
    extents: DataModelCollection[PartitionExtent] = field(
        default_factory=DataModelCollection
    )
