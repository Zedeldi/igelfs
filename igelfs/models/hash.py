"""Data models for hash data of a partition."""

from dataclasses import dataclass
from typing import ClassVar

from igelfs.constants import HASH_HDR_IDENT
from igelfs.models.base import BaseDataModel


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

    def __post_init__(self) -> None:
        """Verify ident string on initialisation."""
        if self.ident != HASH_HDR_IDENT:
            raise ValueError("Unexpected 'ident' for hash header")
