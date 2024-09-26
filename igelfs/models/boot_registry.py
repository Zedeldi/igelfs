"""Data models for the boot registry of a filesystem image."""

from dataclasses import dataclass
from typing import ClassVar

from igelfs.models.base import BaseDataModel
from igelfs.models.collections import DataModelCollection


@dataclass
class BootRegistryEntry(BaseDataModel):
    """Dataclass to describe each entry of boot registry."""

    MODEL_ATTRIBUTE_SIZES: ClassVar[dict[str, int]] = {"flag": 2, "data": 62}

    flag: int  # first 9 bits next, 1 bit next present, 6 bit len key
    data: bytes


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
