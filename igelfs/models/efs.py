"""Data models for extent filesystem structures."""

import hashlib
import io
import os
import tarfile
from dataclasses import dataclass, field
from typing import ClassVar

import lzf
from nacl.secret import Aead

from igelfs.constants import EXTENTFS_MAGIC, IGF_EXTENTFS_DATA_LEN
from igelfs.models.base import BaseDataModel, DataModelMetadata


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
    authenticated: bytes = field(metadata=DataModelMetadata(size=8))
    reserved_3: bytes = field(metadata=DataModelMetadata(size=8))
    data: bytes = field(metadata=DataModelMetadata(size=IGF_EXTENTFS_DATA_LEN))

    def __post_init__(self) -> None:
        """Verify magic string on initialisation."""
        if self.magic != EXTENTFS_MAGIC:
            raise ValueError(f"Unexpected magic '{self.magic}' for extent filesystem")

    def get_nonce(self) -> bytes:
        """Return nonce for extent filesystem encryption."""
        nonce = (self.nonce_1, self.nonce_2)
        hashes = map(lambda data: hashlib.sha256(data).digest(), nonce)
        return bytes([a ^ b for a, b in zip(*hashes)])

    @property
    def payload(self) -> bytes:
        """Return encrypted payload from data."""
        return self.data[: self.size]

    def decrypt(self, key: bytes) -> bytes:
        """
        Decrypt payload with specified key.

        Uses IETF XChacha20-Poly1305 cryptosystem.
        """
        box = Aead(key=key[: Aead.KEY_SIZE])
        return box.decrypt(
            self.payload,
            aad=self.authenticated,
            nonce=self.get_nonce()[: Aead.NONCE_SIZE],
        )

    @classmethod
    def decompress(cls: type["ExtentFilesystem"], data: bytes) -> bytes | None:
        """Return LZF-decompressed data or None if too large."""
        return lzf.decompress(data, cls.LZF_DECOMPRESS_SIZE)

    @staticmethod
    def extract(data: bytes, path: str | os.PathLike, *args, **kwargs) -> None:
        """Extract tar archive in data to path."""
        with io.BytesIO(data) as file:
            with tarfile.open(fileobj=file) as tar:
                tar.extractall(path, *args, **kwargs)
