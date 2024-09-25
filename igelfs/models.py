"""Data models for the IGEL filesystem."""

from dataclasses import dataclass
from typing import ClassVar

from igelfs.base import BaseDataModel, DataModelCollection
from igelfs.constants import (
    DIR_MAX_MINORS,
    IGF_SECT_DATA_LEN,
    IGF_SECT_HDR_LEN,
    MAX_FRAGMENTS,
    SECTION_IMAGE_CRC_START,
)


@dataclass
class BootRegistryEntry(BaseDataModel):
    """Dataclass to describe each entry of boot registry."""

    MODEL_ATTRIBUTE_SIZES: ClassVar[dict[str, int]] = {"flag": 2, "data": 62}

    flag: int  # first 9 bits next, 1 bit next present, 6 bit len key
    data: bytes


@dataclass
class BootRegistryHeader(BaseDataModel):
    """
    Dataclass to handle boot registry header data.

    The boot registry resides in section #0 of the image.
    """

    MODEL_ATTRIBUTE_SIZES: ClassVar[dict[str, int]] = {
        "ident_legacy": 17,
        "magic": 4,
        "hdr_version": 1,
        "boot_id": 21,
        "enc_alg": 1,
        "flags": 2,
        "empty": 82,
        "free": 64,
        "used": 64,
        "dir": 252,
        "reserve": 4,
        "entry": 504 * BootRegistryEntry.get_model_size(),
    }

    ident_legacy: str  # "IGEL BOOTREGISTRY"
    magic: str  # BOOTREG_MAGIC
    hdr_version: int  # 0x01 for the first
    boot_id: str  # boot_id
    enc_alg: int  # encryption algorithm
    flags: int  # flags
    empty: bytes  # placeholder
    free: bytes  # bitmap with free 64 byte blocks
    used: bytes  # bitmap with used 64 byte blocks
    dir: bytes  # directory bitmap (4 bits for each block -> key len)
    reserve: bytes  # placeholder
    entry: DataModelCollection[BootRegistryEntry]  # real data


@dataclass
class SectionHeader(BaseDataModel):
    """Dataclass to handle section header data."""

    MODEL_ATTRIBUTE_SIZES: ClassVar[dict[str, int]] = {
        "crc": 4,
        "magic": 4,
        "section_type": 2,
        "section_size": 2,
        "partition_minor": 4,
        "generation": 2,
        "section_in_minor": 4,
        "next_section": 4,
        "reserved": 6,
    }

    crc: int  # crc of the rest of the section
    magic: int  # magic number (erase count long ago)
    section_type: int
    section_size: int  # log2((section size in bytes) / 65536)
    partition_minor: int  # partition number (driver minor number)
    generation: int  # update generation count
    section_in_minor: int  # n = 0,...,(number of sect.-1)
    next_section: int  # index of the next section or 0xffffffff = end of chain
    reserved: bytes  # section header is 32 bytes but 6 bytes are unused


@dataclass
class Section(BaseDataModel):
    """Dataclass to handle section of an image."""

    MODEL_ATTRIBUTE_SIZES: ClassVar[dict[str, int]] = {
        "header": IGF_SECT_HDR_LEN,
        "data": IGF_SECT_DATA_LEN,
    }
    CRC_OFFSET = SECTION_IMAGE_CRC_START

    header: SectionHeader
    data: bytes

    @property
    def crc(self) -> int:
        """Return CRC32 checksum from header."""
        return self.header.crc


@dataclass
class PartitionHeader(BaseDataModel):
    """Dataclass to handle partition header data."""

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
    hdrlen: int  # length of the complete partition header
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

    minor: int  # a replication of igf_sect_hdr.partition
    type: int  # partition type, a replication of igf_part_hdr.type
    first_fragment: int  # index of the first fragment
    n_fragments: int  # number of additional fragments


@dataclass
class Directory(BaseDataModel):
    """Dataclass to handle directory header data."""

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


@dataclass
class BootsplashHeader(BaseDataModel):
    """Dataclass to handle bootsplash header data."""

    MODEL_ATTRIBUTE_SIZES: ClassVar[dict[str, int]] = {"magic": 14, "num_splashs": 1}

    magic: str  # BOOTSPLASH_MAGIC
    num_splashs: int


@dataclass
class Bootsplash(BaseDataModel):
    """Dataclass to handle bootsplash data."""

    MODEL_ATTRIBUTE_SIZES: ClassVar[dict[str, int]] = {
        "offset": 8,
        "length": 8,
        "ident": 8,
    }

    offset: int
    length: int
    ident: bytes
