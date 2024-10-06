"""Data models for bootsplash structures."""

from dataclasses import dataclass
from typing import ClassVar

from igelfs.constants import BOOTSPLASH_MAGIC
from igelfs.models.base import BaseDataModel


@dataclass
class BootsplashHeader(BaseDataModel):
    """Dataclass to handle bootsplash header data."""

    MODEL_ATTRIBUTE_SIZES: ClassVar[dict[str, int]] = {"magic": 14, "num_splashs": 1}

    magic: str  # BOOTSPLASH_MAGIC
    num_splashs: int

    def __post_init__(self) -> None:
        """Verify magic string on initialisation."""
        if self.magic != BOOTSPLASH_MAGIC:
            raise ValueError(f"Unexpected magic '{self.magic}' for bootsplash header")


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
