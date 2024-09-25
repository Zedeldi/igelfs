"""Data models for the IGEL filesystem."""

from dataclasses import dataclass, field
from typing import ClassVar

from igelfs.base import BaseDataModel, DataModelCollection
from igelfs.constants import (
    DIR_MAX_MINORS,
    IGF_SECT_DATA_LEN,
    IGF_SECT_HDR_LEN,
    HASH_HDR_IDENT,
    MAX_EXTENT_NUM,
    MAX_FRAGMENTS,
    SECTION_IMAGE_CRC_START,
    PartitionType,
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

    def __post_init__(self) -> None:
        """Handle model-specific data post-initialisation."""
        self.type = int.from_bytes(
            self.type.to_bytes(self.MODEL_ATTRIBUTE_SIZES["type"], byteorder="big"),
            byteorder="little",
        )

    def get_type(self) -> PartitionType:
        """Return PartitionType from PartitionHeader instance."""
        return PartitionType(self.type & 0xFF)


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
class HashExclude(BaseDataModel):
    """
    Dataclass to handle hash exclude data.

    Used to mark areas which should be excluded from hashing.
    The start, end and size are based on absolute addresses not relative
    to section or partition headers.
    """

    MODEL_ATTRIBUTE_SIZES: ClassVar[dict[str, int]] = {
        "start": 8,
        "size": 4,
        "repeat": 4,
        "end": 8,
    }

    start: int  # start of area to exclude
    size: int  # size of area to exclude
    repeat: int  # repeat after ... bytes if 0 -> no repeat
    end: int  # end address where the exclude area end (only used if repeat is defined)


@dataclass
class HashHeader(BaseDataModel):
    """Dataclass to handle hash header data."""

    MODEL_ATTRIBUTE_SIZES: ClassVar[dict[str, int]] = {
        "ident": 6,
        "version": 2,
        "signature": 512,
        "count_hash": 8,
        "signature_algo": 1,
        "hash_algo": 1,
        "hash_bytes": 2,
        "blocksize": 4,
        "hash_header_size": 4,
        "hash_block_size": 4,
        "count_excludes": 2,
        "excludes_size": 2,
        "offset_hash": 4,
        "offset_hash_excludes": 4,
        "reserved": 4,
    }

    ident: str  # Ident string "chksum"
    # version number of header probably use with flags
    # something like version = version & 0xff; if (version |= FLAG ...)
    version: int
    signature: bytes  # 512 Bytes -> 4096bit signature length
    count_hash: int  # count of hash values
    signature_algo: (
        int  # Used signature algo (which is a define like HASH_SIGNATURE_TYPE_NONE)
    )
    hash_algo: int  # Used hash algo (which is a define like HASH_ALGO_TYPE_NONE)
    hash_bytes: int  # bytes used for hash sha256 -> 32bytes, sha512 -> 64bytes
    blocksize: int  # size of data used for hashing
    hash_header_size: int  # size of the hash_header (with hash excludes)
    hash_block_size: int  # size of the hash values block
    count_excludes: int  # count of struct igel_hash_exclude variables
    excludes_size: int  # size of struct igel_hash_exclude variables in Bytes
    offset_hash: int  # offset of hash block from section header in bytes
    offset_hash_excludes: (
        int  # offset of hash_excludes block from start of igel_hash_header in bytes
    )
    reserved: bytes  # reserved for further use/padding for excludes alignment


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
    """
    Dataclass to handle section of an image.

    Not all sections have a partition or hash header. Data is parsed
    post-initialisation to add these attributes.
    """

    MODEL_ATTRIBUTE_SIZES: ClassVar[dict[str, int]] = {
        "header": IGF_SECT_HDR_LEN,
        "data": IGF_SECT_DATA_LEN,
    }
    CRC_OFFSET = SECTION_IMAGE_CRC_START

    header: SectionHeader
    partition: PartitionHeader | None = field(init=False)
    hash: HashHeader | None = field(init=False)
    data: bytes

    def __post_init__(self) -> None:
        """Parse data into optional additional attributes."""
        partition, data = PartitionHeader.from_bytes_with_remaining(self.data)
        if partition.hdrlen != PartitionHeader.get_model_size():
            self.partition = None
        else:
            self.partition = partition
            self.data = data
        try:
            self.hash, data = HashHeader.from_bytes_with_remaining(self.data)
            if self.hash.ident != HASH_HDR_IDENT:
                raise ValueError("Unexpected 'ident' for hash header")
            self.data = data
        except Exception:
            self.hash = None

    @property
    def crc(self) -> int:
        """Return CRC32 checksum from header."""
        return self.header.crc

    @property
    def end_of_chain(self) -> bool:
        """Return whether this section is the last in the chain."""
        return self.header.next_section == 0xffffffff


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
class Directory(BaseDataModel):
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

    def find_fragment_by_partition_minor(self, partition_minor: int) -> FragmentDescriptor | None:
        """Return FragmentDescriptor from PartitionDescriptor with matching minor."""
        if not (partition := self.find_partition_by_partition_minor(partition_minor)):
            return None
        return self.fragment[partition.first_fragment]


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
