"""Helper module for cryptographic operations."""

import base64
import hashlib

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers.algorithms import AES
from cryptography.hazmat.primitives.ciphers.modes import XTS
from nacl import pwhash
from nacl.secret import Aead

STATIC_KEY_1 = b"\x6f\x86\x89\xe7\x8a\xc0Mu\xf1P\xf1;\xf1\xf2\xf7\x86\x93\xf2\x99\xc5\x11hk9\xad\xc2Q\xe6\\V\xf8K"
STATIC_KEY_2 = b"\x655\xd4\x19\xd6,9\x80\xe9\xe9\x87Lk\x88#\x00\x94)\xe4\xefH\xfb\xd2\xdfo\xb3aA\xbek\xd4\xf7o"
STATIC_KEY = bytes(
    0xFF - (byte_2 ^ (byte_1 ^ 0x57))  # unsigned bitwise not
    for byte_1, byte_2 in zip(STATIC_KEY_1, STATIC_KEY_2)
)
BASE64_KEY_1 = "bDF0Ib7m+zCS9Fu0Z9hdJ5MnfPsbu8y+7cH75TFHf+Q="
BASE64_KEY_2 = "3aiFZE00oVQXIr3C/rttDo3Q+XsG4grpPGIYVgCpzNA="
DEFAULT_PASSWORD = b"default"


class CryptoHelper:
    """Helper class with static methods for cryptographic operations."""

    # KDF_CONFIG[level] = (opslimit, memlimit)
    KDF_CONFIG: list[tuple[int, int]] = [  # index represents level
        (3, 128000000),  # default values
        (7, 8000000),  # level = 1
        (2, 1024000000),
        (3, 256000000),
        (3, 512000000),
        (4, 128000000),
    ]

    @staticmethod
    def aead_xchacha20_poly1305_ietf_decrypt(
        data: bytes, aad: bytes, nonce: bytes, key: bytes
    ) -> bytes:
        """
        Decrypt data with specified key and nonce, verifying aad.

        Uses IETF XChacha20-Poly1305 cryptosystem.
        """
        box = Aead(key=key[: Aead.KEY_SIZE])
        return box.decrypt(
            data,
            aad=aad,
            nonce=nonce[: Aead.NONCE_SIZE],
        )

    @staticmethod
    def aes_xts_decrypt(data: bytes, key: bytes) -> bytes:
        """Decrypt data with specified key, with sliced IV."""
        iv = key[32:]  # last 32 bytes of key, assuming key is 64 bytes
        cipher = Cipher(AES(key), mode=XTS(iv[:16]), backend=default_backend())
        return cipher.decryptor().update(data)

    @staticmethod
    def get_extent_key(
        boot_id: str, base64_key: str | None = None, key_size: int = Aead.KEY_SIZE
    ) -> bytes:
        """Return key derived from boot_id for extent filesystem."""
        # initial values are sha256 hash of boot_id and a static key
        boot_id_hash = hashlib.sha256(boot_id.encode()).digest()
        # xor boot_id_hash with static key
        result = bytes([boot_id_hash[idx] ^ STATIC_KEY[idx] for idx in range(key_size)])
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

    @classmethod
    def _get_master_key(
        cls: type["CryptoHelper"],
        password: bytes,
        salt: bytes,
        pub: bytes,
        priv: bytes,
        level: int,
    ) -> bytes:
        """Return master key for key decryption from password."""
        # memlimit and opslimit dependent on level
        try:
            opslimit, memlimit = cls.KDF_CONFIG[level]
        except IndexError:
            opslimit, memlimit = cls.KDF_CONFIG[0]
        derived_key = (
            pwhash.argon2id.kdf(
                32, password, salt, opslimit=opslimit, memlimit=memlimit
            )
            + pub
        )
        derived_key_hash = hashlib.sha512(derived_key).digest()
        return cls.aes_xts_decrypt(priv, derived_key_hash)

    @classmethod
    def get_master_key(
        cls: type["CryptoHelper"],
        extent_key: bytes,
        salt: bytes,
        pub: bytes,
        priv: bytes,
        level: int,
    ) -> bytes:
        """Return master key for key decryption from extent key."""
        password = base64.b64encode(base64.b64decode(extent_key)[:20])
        return cls._get_master_key(
            password=password, salt=salt, pub=pub, priv=priv, level=level
        )

    @classmethod
    def get_default_key(
        cls: type["CryptoHelper"],
        salt: bytes,
        pub: bytes,
        priv: bytes,
        level: int,
    ) -> bytes:
        """Return default master key for key decryption."""
        return cls._get_master_key(
            password=DEFAULT_PASSWORD, salt=salt, pub=pub, priv=priv, level=level
        )
