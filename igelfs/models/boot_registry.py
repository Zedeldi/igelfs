"""Data models for the boot registry of a filesystem image."""

from abc import abstractmethod
from dataclasses import dataclass
from functools import partial
from typing import ClassVar

from igelfs.constants import BOOTREG_IDENT, BOOTREG_MAGIC, IGEL_BOOTREG_SIZE
from igelfs.models.base import BaseDataModel
from igelfs.models.collections import DataModelCollection


@dataclass
class BootRegistryEntry(BaseDataModel):
    """Dataclass to describe each entry of boot registry."""

    MODEL_ATTRIBUTE_SIZES: ClassVar[dict[str, int]] = {"flag": 2, "data": 62}

    flag: int  # first 9 bits next, 1 bit next present, 6 bit len key
    data: bytes

    @property
    def _flag_bits(self) -> tuple[str, str, str]:
        """
        Split flag into tuple of bits.

        9 Bits: Next Block Index
        1 Bit: Next Block Present
        6 Bits: Key Length
        """
        bits = (
            bin(
                int(
                    self.flag.to_bytes(self.MODEL_ATTRIBUTE_SIZES["flag"], "big").hex(),
                    base=16,
                )
            )
            .removeprefix("0b")
            .zfill(16)
        )
        return (bits[:9], bits[9:10], bits[10:])

    @property
    def _flag_values(self) -> tuple[int, int, int]:
        """
        Return tuple of integers for flag values.

        Tuple consists of next block index, next block present, key length
        as integers.
        """
        return tuple(map(partial(int, base=2), self._flag_bits))

    @property
    def next_block_index(self) -> int:
        """Return index of next block."""
        return self._flag_values[0]

    @property
    def next_block_present(self) -> bool:
        """Return whether next block is present."""
        return bool(self._flag_values[1])

    @property
    def key_length(self) -> int:
        """Return length of key for entry."""
        return self._flag_values[2]

    @property
    def key(self) -> str:
        """Return key for entry."""
        return self.data[: self.key_length].decode()

    @property
    def value(self) -> str:
        """Return value for entry."""
        return self.data[self.key_length :].rstrip(b"\x00").decode()


@dataclass
class BaseBootRegistryHeader(BaseDataModel):
    """Base class for boot registry header."""

    def __post_init__(self) -> None:
        """Verify identity string on initialisation."""
        if self.ident_legacy != BOOTREG_IDENT:
            raise ValueError(
                f"Unexpected identity string '{self.ident_legacy}' for boot registry"
            )

    @abstractmethod
    def get_entries(self) -> dict[str, str]:
        """Return dictionary of all boot registry entries."""
        ...


@dataclass
class BootRegistryHeader(BaseBootRegistryHeader):
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

    def __post_init__(self) -> None:
        """Verify magic string on initialisation."""
        super().__post_init__()
        if self.magic != BOOTREG_MAGIC:
            raise ValueError(
                f"Unexpected magic string '{self.magic}' for boot registry"
            )

    def get_entries(self) -> dict[str, str]:
        """Return dictionary of all boot registry entries."""
        entries = {}
        key = None
        for entry in self.entry:
            if not entry.value:
                continue
            if key:  # value continues previous entry
                entries[key] += entry.value
            else:  # new value
                entries[entry.key] = entry.value
            if entry.next_block_present:  # preserve key for next entry
                key = key or entry.key
            else:  # reset key
                key = None
        return entries


@dataclass
class BootRegistryHeaderLegacy(BaseBootRegistryHeader):
    """
    Dataclass to handle legacy boot registry header data.

    The boot registry resides in section #0 of the image.
    """

    MODEL_ATTRIBUTE_SIZES: ClassVar[dict[str, int]] = {
        "ident_legacy": 17,
        "entry": IGEL_BOOTREG_SIZE - 17,
    }

    ident_legacy: str
    entry: bytes

    def get_entries(self) -> dict[str, str]:
        """Return dictionary of all boot registry entries."""
        entries = {}
        for entry in self.entry.decode().splitlines():
            if not entry:
                continue
            if entry == "EOF":
                break
            key, value = entry.split("=")
            entries[key] = value
        return entries


class BootRegistryHeaderFactory:
    """Class to handle returning the correct boot registry header model."""

    @staticmethod
    def is_legacy_boot_registry(data: bytes) -> bool:
        """Return whether bytes represent a legacy boot registry header."""
        ident_legacy = BootRegistryHeader.MODEL_ATTRIBUTE_SIZES["ident_legacy"]
        magic = BootRegistryHeader.MODEL_ATTRIBUTE_SIZES["magic"]
        if data[ident_legacy : ident_legacy + magic].decode() == BOOTREG_MAGIC:
            return False
        return True

    @classmethod
    def from_bytes(
        cls: type["BootRegistryHeaderFactory"], data: bytes
    ) -> BootRegistryHeader | BootRegistryHeaderLegacy:
        """Return appropriate boot registry header model from bytes."""
        if cls.is_legacy_boot_registry(data):
            return BootRegistryHeaderLegacy.from_bytes(data)
        return BootRegistryHeader.from_bytes(data)
