"""Data models for extent filesystem structures."""

import base64
import hashlib
import io
import json
import os
import tarfile
from dataclasses import dataclass, field
from typing import Any, ClassVar

import lzf
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers.algorithms import AES
from cryptography.hazmat.primitives.ciphers.modes import XTS
from nacl import pwhash
from nacl.secret import Aead

from igelfs.constants import EXTENTFS_MAGIC, IGF_EXTENTFS_DATA_LEN
from igelfs.models.base import BaseDataModel, DataModelMetadata
from igelfs.utils import tarfile_from_bytes

STATIC_KEY_1 = b"\x6f\x86\x89\xe7\x8a\xc0Mu\xf1P\xf1;\xf1\xf2\xf7\x86\x93\xf2\x99\xc5\x11hk9\xad\xc2Q\xe6\\V\xf8K"
STATIC_KEY_2 = b"\x655\xd4\x19\xd6,9\x80\xe9\xe9\x87Lk\x88#\x00\x94)\xe4\xefH\xfb\xd2\xdfo\xb3aA\xbek\xd4\xf7o"
BASE64_KEY_1 = "bDF0Ib7m+zCS9Fu0Z9hdJ5MnfPsbu8y+7cH75TFHf+Q="
BASE64_KEY_2 = "3aiFZE00oVQXIr3C/rttDo3Q+XsG4grpPGIYVgCpzNA="
DEFAULT_PASSWORD = b"default"
KDF_CONFIG = [  # index represents level
    (3, 128000000),  # default values
    (7, 8000000),  # level = 1
    (2, 1024000000),
    (3, 256000000),
    (3, 512000000),
    (4, 128000000),
]


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
        with tarfile_from_bytes(data) as tar:
            tar.extractall(path, *args, **kwargs)

    @staticmethod
    def _extract_file(data: bytes, member: str | tarfile.TarInfo) -> bytes:
        """Extract member from tar archive in data as bytes."""
        with tarfile_from_bytes(data) as tar:
            file = tar.extractfile(member)
            if not file:
                raise ValueError(f"Member {member} does not exist")
            return file.read()

    @classmethod
    def get_kmlconfig(cls: type["ExtentFilesystem"], data: bytes) -> dict[str, Any]:
        """Return dictionary of kmlconfig JSON data."""
        with io.BytesIO(cls._extract_file(data, "kmlconfig.json")) as file:
            return json.load(file)

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

    @staticmethod
    def _aes_xts_decrypt(data: bytes, key: bytes) -> bytes:
        """Decrypt data with specified key, with sliced IV."""
        iv = key[32:]  # last 32 bytes of key, assuming key is 64 bytes
        cipher = Cipher(AES(key), mode=XTS(iv[:16]), backend=default_backend())
        return cipher.decryptor().update(data)

    @classmethod
    def get_master_key(
        cls: type["ExtentFilesystem"], config: dict[str, Any], key: bytes, slot: int = 0
    ) -> bytes:
        """Return master key for key decryption."""
        password = base64.b64encode(base64.b64decode(key)[:20])
        salt = base64.b64decode(config["system"]["salt"])
        pub = base64.b64decode(config["slots"][slot]["pub"])
        priv = base64.b64decode(config["slots"][slot]["priv"])
        level = config["system"]["level"]
        # memlimit and opslimit dependent on level
        try:
            opslimit, memlimit = KDF_CONFIG[level]
        except IndexError:
            opslimit, memlimit = KDF_CONFIG[0]
        derived_key = (
            pwhash.argon2id.kdf(
                32, password, salt, opslimit=opslimit, memlimit=memlimit
            )
            + pub
        )
        derived_key_hash = hashlib.sha512(derived_key).digest()
        return cls._aes_xts_decrypt(priv, derived_key_hash)

    @classmethod
    def get_key_for_name(
        cls: type["ExtentFilesystem"],
        config: dict[str, Any],
        name: str,
        master_key: bytes,
    ) -> bytes:
        """Return key for name from config."""
        key = base64.b64decode(config["keys"][name])
        return cls._aes_xts_decrypt(key, master_key)
