"""Data models for the boot registry of a filesystem image."""

from dataclasses import dataclass
from functools import partial
from typing import ClassVar

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
