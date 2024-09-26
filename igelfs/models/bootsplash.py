"""Data models for bootsplash structures."""

from dataclasses import dataclass
from typing import ClassVar

from igelfs.models.base import BaseDataModel


@dataclass
class BootsplashHeader(BaseDataModel):
    """Dataclass to handle bootsplash header data."""

    MODEL_ATTRIBUTE_SIZES: ClassVar[dict[str, int]] = {"magic": 14, "num_splashs": 1}

    magic: str  # BOOTSPLASH_MAGIC
    num_splashs: int


@dataclass
class Bootsplash(BaseDataModel):
    """Dataclass to handle bootsplash data."""

    MODEL_ATTRIBUTE_SIZES: ClassVar[dict[str, int]] = {
        "offset": 8,
        "length": 8,
        "ident": 8,
    }

    offset: int
    length: int
    ident: bytes
