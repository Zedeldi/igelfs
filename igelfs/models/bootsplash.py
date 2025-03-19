"""Data models for bootsplash structures."""

import io
from dataclasses import dataclass, field

from PIL import Image

from igelfs.constants import BOOTSPLASH_MAGIC
from igelfs.models.base import BaseDataGroup, BaseDataModel, DataModelMetadata
from igelfs.models.collections import DataModelCollection


@dataclass
class BootsplashHeader(BaseDataModel):
    """Dataclass to handle bootsplash header data."""

    magic: str = field(  # BOOTSPLASH_MAGIC
        metadata=DataModelMetadata(size=14, default=BOOTSPLASH_MAGIC)
    )
    num_splashs: int = field(metadata=DataModelMetadata(size=1))

    def __post_init__(self) -> None:
        """Verify magic string on initialisation."""
        if self.magic != BOOTSPLASH_MAGIC:
            raise ValueError(f"Unexpected magic '{self.magic}' for bootsplash header")


@dataclass
class Bootsplash(BaseDataModel):
    """Dataclass to handle bootsplash data."""

    offset: int = field(metadata=DataModelMetadata(size=8))
    length: int = field(metadata=DataModelMetadata(size=8))
    ident: bytes = field(metadata=DataModelMetadata(size=8))


@dataclass
class BootsplashExtent(BaseDataGroup):
    """
    Dataclass to handle data of a bootsplash partition extent.

    Extent is not a fixed size so cannot use mapping of attribute to sizes.
    """

    header: BootsplashHeader
    splashes: DataModelCollection[Bootsplash]
    data: bytes

    @classmethod
    def from_bytes(cls: type["BootsplashExtent"], data: bytes) -> "BootsplashExtent":
        """Return bootsplash extent model from bytes."""
        header, data = BootsplashHeader.from_bytes_with_remaining(data)
        splashes: DataModelCollection[Bootsplash] = DataModelCollection()
        for _ in range(header.num_splashs):
            splash, data = Bootsplash.from_bytes_with_remaining(data)
            splashes.append(splash)
        return cls(header=header, splashes=splashes, data=data)

    def _get_image_data(self) -> list[bytes]:
        """Return list of bytes for images."""
        offset = self.header.get_actual_size() + self.splashes.get_actual_size()
        return [
            self.data[splash.offset - offset : splash.offset - offset + splash.length]
            for splash in self.splashes
        ]

    def get_images(self) -> list[Image.Image]:
        """Return list of image instances."""
        return [Image.open(io.BytesIO(image)) for image in self._get_image_data()]
