"""Data models for extent filesystem structures."""

import hashlib
import os
import tarfile
from dataclasses import dataclass, field
from typing import ClassVar

try:
    import lzf

    _IS_LZF_AVAILABLE = True
except ImportError:
    _IS_LZF_AVAILABLE = False

from igelfs.constants import EXTENTFS_MAGIC, IGF_EXTENTFS_DATA_LEN

try:
    from igelfs.crypto import CryptoHelper

    _IS_CRYPTO_AVAILABLE = True
except ImportError:
    _IS_CRYPTO_AVAILABLE = False
from igelfs.models.base import BaseDataModel, DataModelMetadata
from igelfs.utils import tarfile_from_bytes


@dataclass
class ExtentFilesystem(BaseDataModel):
    """Dataclass to handle extent filesystem data."""

    LZF_DECOMPRESS_SIZE: ClassVar[int] = 4096

    magic: str = field(  # EXTENTFS_MAGIC
        metadata=DataModelMetadata(size=4, default=EXTENTFS_MAGIC)
    )
    reserved_1: bytes = field(metadata=DataModelMetadata(size=4))
    nonce_1: bytes = field(metadata=DataModelMetadata(size=8))
    nonce_2: bytes = field(metadata=DataModelMetadata(size=1))
    reserved_2: bytes = field(metadata=DataModelMetadata(size=7))
    size: int = field(metadata=DataModelMetadata(size=8))
    aad: bytes = field(metadata=DataModelMetadata(size=8))
    reserved_3: bytes = field(metadata=DataModelMetadata(size=8))
    data: bytes = field(metadata=DataModelMetadata(size=IGF_EXTENTFS_DATA_LEN))

    def __post_init__(self) -> None:
        """Verify magic string on initialisation."""
        if self.magic != EXTENTFS_MAGIC:
            raise ValueError(f"Unexpected magic '{self.magic}' for extent filesystem")

    @property
    def nonce(self) -> bytes:
        """Return nonce for extent filesystem encryption."""
        nonce = (self.nonce_1, self.nonce_2)
        hashes = map(lambda data: hashlib.sha256(data).digest(), nonce)
        return bytes([a ^ b for a, b in zip(*hashes)])

    @property
    def payload(self) -> bytes:
        """Return encrypted payload from data."""
        return self.data[: self.size]

    def decrypt(self, key: bytes) -> bytes:
        """Decrypt payload with specified key."""
        if not _IS_CRYPTO_AVAILABLE:
            raise ImportError("Cryptographic functionality is not available")
        return CryptoHelper.aead_xchacha20_poly1305_ietf_decrypt(
            self.payload,
            aad=self.aad,
            nonce=self.nonce,
            key=key,
        )

    @classmethod
    def decompress(cls: type["ExtentFilesystem"], data: bytes) -> bytes | None:
        """Return LZF-decompressed data or None if too large."""
        if not _IS_LZF_AVAILABLE:
            raise ImportError("lzf functionality is not available")
        return lzf.decompress(data, cls.LZF_DECOMPRESS_SIZE)

    @staticmethod
    def extract(data: bytes, path: str | os.PathLike, *args, **kwargs) -> None:
        """Extract tar archive in data to path."""
        with tarfile_from_bytes(data) as tar:
            tar.extractall(path, *args, **kwargs)

    @staticmethod
    def extract_file(data: bytes, member: str | tarfile.TarInfo) -> bytes:
        """Extract member from tar archive in data as bytes."""
        with tarfile_from_bytes(data) as tar:
            file = tar.extractfile(member)
            if not file:
                raise ValueError(f"Cannot read member {member}")
            return file.read()
