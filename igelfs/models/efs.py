"""Data models for extent filesystem structures."""

import base64
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

STATIC_KEY_1 = b"\x6f\x86\x89\xe7\x8a\xc0Mu\xf1P\xf1;\xf1\xf2\xf7\x86\x93\xf2\x99\xc5\x11hk9\xad\xc2Q\xe6\\V\xf8K"
STATIC_KEY_2 = b"\x655\xd4\x19\xd6,9\x80\xe9\xe9\x87Lk\x88#\x00\x94)\xe4\xefH\xfb\xd2\xdfo\xb3aA\xbek\xd4\xf7o"
BASE64_KEY_1 = "bDF0Ib7m+zCS9Fu0Z9hdJ5MnfPsbu8y+7cH75TFHf+Q="
BASE64_KEY_2 = "3aiFZE00oVQXIr3C/rttDo3Q+XsG4grpPGIYVgCpzNA="


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

    @staticmethod
    def derive_key(
        boot_id: str, base64_key: str | None = None, key_size: int = Aead.KEY_SIZE
    ) -> bytes:
        """Return key derived from boot_id for extent filesystem."""
        # initial values are sha256 hash of boot_id
        boot_id_hash = hashlib.sha256(boot_id.encode()).digest()
        # and a static key
        key = [
            0xFF - (byte_2 ^ (byte_1 ^ 0x57))  # unsigned bitwise not
            for byte_1, byte_2 in zip(STATIC_KEY_1, STATIC_KEY_2)
        ]
        # xor boot_id_hash with static key
        result = bytes([boot_id_hash[idx] ^ key[idx] for idx in range(key_size)])
        # sha256 result maximum of 41 times
        iterations = (sum(result) & 0x1F) + 0xA
        for _ in range(iterations):
            result = hashlib.sha256(result).digest()

        if base64_key:
            bin_key = base64.b64decode(base64_key)
            for _ in range(iterations + 1):
                bin_key = hashlib.sha256(bin_key).digest()
            result = bytes([result[idx] ^ bin_key[idx] for idx in range(key_size)])

        # return base64 encoded result
        return base64.b64encode(result)
