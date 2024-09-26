"""Data models for a section."""

from dataclasses import dataclass, field
from typing import ClassVar

from igelfs.constants import (
    HASH_HDR_IDENT,
    IGF_SECT_DATA_LEN,
    IGF_SECT_HDR_LEN,
    SECTION_IMAGE_CRC_START,
)
from igelfs.models.base import BaseDataModel
from igelfs.models.hash import HashHeader
from igelfs.models.partition import PartitionHeader


@dataclass
class SectionHeader(BaseDataModel):
    """Dataclass to handle section header data."""

    MODEL_ATTRIBUTE_SIZES: ClassVar[dict[str, int]] = {
        "crc": 4,
        "magic": 4,
        "section_type": 2,
        "section_size": 2,
        "partition_minor": 4,
        "generation": 2,
        "section_in_minor": 4,
        "next_section": 4,
        "reserved": 6,
    }

    crc: int  # crc of the rest of the section
    magic: int  # magic number (erase count long ago)
    section_type: int
    section_size: int  # log2((section size in bytes) / 65536)
    partition_minor: int  # partition number (driver minor number)
    generation: int  # update generation count
    section_in_minor: int  # n = 0,...,(number of sect.-1)
    next_section: int  # index of the next section or 0xffffffff = end of chain
    reserved: bytes  # section header is 32 bytes but 6 bytes are unused


@dataclass
class Section(BaseDataModel):
    """
    Dataclass to handle section of an image.

    Not all sections have a partition or hash header. Data is parsed
    post-initialisation to add these attributes.
    """

    MODEL_ATTRIBUTE_SIZES: ClassVar[dict[str, int]] = {
        "header": IGF_SECT_HDR_LEN,
        "data": IGF_SECT_DATA_LEN,
    }
    CRC_OFFSET = SECTION_IMAGE_CRC_START

    header: SectionHeader
    partition: PartitionHeader | None = field(init=False)
    hash: HashHeader | None = field(init=False)
    data: bytes

    def __post_init__(self) -> None:
        """Parse data into optional additional attributes."""
        partition, data = PartitionHeader.from_bytes_with_remaining(self.data)
        if partition.hdrlen != PartitionHeader.get_model_size():
            self.partition = None
        else:
            self.partition = partition
            self.data = data
        try:
            self.hash, data = HashHeader.from_bytes_with_remaining(self.data)
            if self.hash.ident != HASH_HDR_IDENT:
                raise ValueError("Unexpected 'ident' for hash header")
            self.data = data
        except Exception:
            self.hash = None

    @property
    def crc(self) -> int:
        """Return CRC32 checksum from header."""
        return self.header.crc

    @property
    def end_of_chain(self) -> bool:
        """Return whether this section is the last in the chain."""
        return self.header.next_section == 0xFFFFFFFF
