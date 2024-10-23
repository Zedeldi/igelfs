"""Data models for hash data of a partition."""

import hashlib
from dataclasses import dataclass
from typing import ClassVar

import rsa

from igelfs.constants import HASH_HDR_IDENT
from igelfs.keys import HSM_PUBLIC_KEY
from igelfs.models.base import BaseDataGroup, BaseDataModel
from igelfs.models.collections import DataModelCollection


@dataclass
class HashInformation(BaseDataModel):
    """Dataclass to handle hash information data."""

    MODEL_ATTRIBUTE_SIZES: ClassVar[dict[str, int]] = {
        "offset_cache": 4,
        "offset_hashes": 4,
        "count_blocks": 4,
        "block_size": 4,
        "count_excludes": 2,
        "hash_size": 2,
    }

    offset_cache: int
    offset_hashes: int
    count_blocks: int
    block_size: int
    count_excludes: int
    hash_size: int


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

    def get_excluded_indices(self) -> list[int]:
        """Return list of excluded indices for hash."""
        if self.repeat == 0:
            return list(range(self.start, self.start + self.size))
        indices = []
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
        try:
            return (
                rsa.verify(data, self.header.signature[:256], HSM_PUBLIC_KEY)
                == "SHA-256"
            )
        except rsa.VerificationError:
            return False
