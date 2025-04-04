"""Data models for hash data of a partition."""

import hashlib
from dataclasses import dataclass, field

import rsa

from igelfs.constants import HASH_HDR_IDENT
from igelfs.keys import IGEL_PUBLIC_KEYS
from igelfs.models.base import BaseDataGroup, BaseDataModel, DataModelMetadata
from igelfs.models.collections import DataModelCollection


@dataclass
class HashInformation(BaseDataModel):
    """Dataclass to handle hash information data."""

    offset_cache: int = field(metadata=DataModelMetadata(size=4))
    offset_hashes: int = field(metadata=DataModelMetadata(size=4))
    count_blocks: int = field(metadata=DataModelMetadata(size=4))
    block_size: int = field(metadata=DataModelMetadata(size=4))
    count_excludes: int = field(metadata=DataModelMetadata(size=2))
    hash_size: int = field(metadata=DataModelMetadata(size=2))


@dataclass
class HashExclude(BaseDataModel):
    """
    Dataclass to handle hash exclude data.

    Used to mark areas which should be excluded from hashing.
    The start, end and size are based on absolute addresses not relative
    to section or partition headers.

    The following bytes are normally excluded for each section (inclusive):
    -   0-3 => SectionHeader.crc
    -   16-17 => SectionHeader.generation
    -   22-25 => SectionHeader.next_section

    The following bytes are normally excluded for section zero (inclusive, shifted by partition extents):
    -   164-675 => HashHeader.signature
    -   836-836 + (HashHeader.hash_bytes * HashHeader.count_hash) => Section.hash_value
    """

    start: int = field(metadata=DataModelMetadata(size=8))  # start of area to exclude
    size: int = field(metadata=DataModelMetadata(size=4))  # size of area to exclude
    repeat: int = field(  # repeat after ... bytes if 0 -> no repeat
        metadata=DataModelMetadata(size=4)
    )
    # end address where the exclude area ends (only used if repeat is not 0)
    end: int = field(metadata=DataModelMetadata(size=8))

    def get_excluded_indices(self) -> list[int]:
        """Return list of excluded indices for hash."""
        if self.repeat == 0:
            return list(range(self.start, self.start + self.size))
        indices: list[int] = []
        for offset in range(0, self.end, self.repeat):
            start = self.start + offset
            indices.extend(range(start, start + self.size))
        return indices

    @staticmethod
    def get_excluded_indices_from_collection(
        excludes: DataModelCollection["HashExclude"],
    ) -> list[int]:
        """Return list of excluded indices for all hash excludes."""
        indices = []
        for exclude in excludes:
            indices.extend(exclude.get_excluded_indices())
        return indices


@dataclass
class HashHeader(BaseDataModel):
    """Dataclass to handle hash header data."""

    ident: str = field(  # Ident string "chksum"
        metadata=DataModelMetadata(size=6, default=HASH_HDR_IDENT)
    )
    # version number of header - possibly used with flags
    # e.g. version = version & 0xff; if (version |= FLAG ...)
    version: int = field(metadata=DataModelMetadata(size=2))
    signature: bytes = field(  # 512 bytes -> 4096-bit signature length
        metadata=DataModelMetadata(size=512)
    )
    count_hash: int = field(metadata=DataModelMetadata(size=8))  # count of hash values
    # Used signature algorithm (e.g. HASH_SIGNATURE_TYPE_NONE)
    signature_algo: int = field(metadata=DataModelMetadata(size=1))
    # Used hash algorithm (e.g. HASH_ALGO_TYPE_NONE)
    hash_algo: int = field(metadata=DataModelMetadata(size=1))
    # bytes used for hash sha256 -> 32 bytes, sha512 -> 64 bytes
    hash_bytes: int = field(metadata=DataModelMetadata(size=2))
    blocksize: int = field(  # size of data used for hashing
        metadata=DataModelMetadata(size=4)
    )
    hash_header_size: int = field(  # size of the hash_header (with hash excludes)
        metadata=DataModelMetadata(size=4)
    )
    hash_block_size: int = field(  # size of the hash values block
        metadata=DataModelMetadata(size=4)
    )
    count_excludes: int = field(  # count of HashExclude models
        metadata=DataModelMetadata(size=2)
    )
    excludes_size: int = field(  # size of HashExclude models in bytes
        metadata=DataModelMetadata(size=2)
    )
    offset_hash: int = field(  # offset of hash block from section header in bytes
        metadata=DataModelMetadata(size=4)
    )
    # offset of hash excludes block from start of hash header in bytes
    offset_hash_excludes: int = field(metadata=DataModelMetadata(size=4))
    # reserved for further use/padding for excludes alignment
    reserved: bytes = field(metadata=DataModelMetadata(size=4))

    def __post_init__(self) -> None:
        """Verify ident string on initialisation."""
        if self.ident != HASH_HDR_IDENT:
            raise ValueError(f"Unexpected ident '{self.ident}' for hash header")

    def get_hash_information(self) -> HashInformation:
        """Return HashInformation instance for HashHeader."""
        offset_cache = HashInformation.get_model_size() + (
            self.count_excludes * self.excludes_size
        )
        offset_hashes = offset_cache + self.count_hash
        return HashInformation(
            offset_cache=offset_cache,
            offset_hashes=offset_hashes,
            count_blocks=self.count_hash,
            block_size=self.blocksize,
            count_excludes=self.count_excludes,
            hash_size=self.hash_bytes,
        )


@dataclass
class Hash(BaseDataGroup):
    """Dataclass to store and handle hash-related data models."""

    header: HashHeader
    excludes: DataModelCollection[HashExclude]
    values: bytes

    def get_hashes(self) -> list[bytes]:
        """Return list of hashes as bytes from hash values."""
        return [
            chunk
            for chunk in [
                self.values[i : i + self.header.hash_bytes]
                for i in range(0, self.header.hash_block_size, self.header.hash_bytes)
            ]
        ]

    def get_hash(self, index: int) -> bytes:
        """Return hash for specified index."""
        return self.get_hashes()[index]

    def calculate_hash(self, data: bytes) -> bytes:
        """Return hash of data."""
        return hashlib.blake2b(data, digest_size=self.header.hash_bytes).digest()

    def verify_signature(self) -> bool:
        """Verify signature of hash block (excludes + values)."""
        data = self.excludes.to_bytes() + self.values
        for public_key in IGEL_PUBLIC_KEYS:
            try:
                return (
                    rsa.verify(data, self.header.signature.rstrip(b"\x00"), public_key)
                    == "SHA-256"
                )
            except rsa.VerificationError:
                pass
        else:
            return False
