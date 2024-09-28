"""Data models for a section."""

from dataclasses import dataclass, field
from typing import ClassVar

from igelfs.constants import (
    IGF_SECT_DATA_LEN,
    IGF_SECT_HDR_LEN,
    IGF_SECT_HDR_MAGIC,
    SECTION_IMAGE_CRC_START,
)
from igelfs.models.base import BaseDataModel
from igelfs.models.collections import DataModelCollection
from igelfs.models.hash import HashExclude, HashHeader
from igelfs.models.partition import PartitionExtent, PartitionHeader


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

    def __post_init__(self) -> None:
        """Verify magic number on initialisation."""
        if self.magic != IGF_SECT_HDR_MAGIC:
            raise ValueError(f"Unexpected magic '{self.magic}' for section header")


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
    extents: DataModelCollection[PartitionExtent] | None = field(init=False)
    hash: HashHeader | None = field(init=False)
    hash_excludes: DataModelCollection[HashExclude] | None = field(init=False)
    hash_value: bytes | None = field(init=False)
    data: bytes

    def __post_init__(self) -> None:
        """Parse data into optional additional attributes."""
        # Partition
        try:  # Partition header
            self.partition, self.data = PartitionHeader.from_bytes_with_remaining(
                self.data
            )
        except ValueError:
            self.partition = None
            self.extents = None
        else:  # Partition extents
            self.extents = DataModelCollection()
            for _ in range(self.partition.n_extents):
                extent, self.data = PartitionExtent.from_bytes_with_remaining(self.data)
                self.extents.append(extent)

        # Hashing
        try:  # Hash header
            self.hash, self.data = HashHeader.from_bytes_with_remaining(self.data)
        except (UnicodeDecodeError, ValueError):
            self.hash = None
            self.hash_excludes = None
            self.hash_value = None
        else:  # Hash excludes
            self.hash_excludes = DataModelCollection()
            for _ in range(self.hash.count_excludes):
                hash_exclude, self.data = HashExclude.from_bytes_with_remaining(
                    self.data
                )
                self.hash_excludes.append(hash_exclude)
            self.hash_value, self.data = (
                self.data[: self.hash.hash_block_size],
                self.data[self.hash.hash_block_size :],
            )

    @property
    def crc(self) -> int:
        """Return CRC32 checksum from header."""
        return self.header.crc

    @property
    def end_of_chain(self) -> bool:
        """Return whether this section is the last in the chain."""
        return self.header.next_section == 0xFFFFFFFF

    @staticmethod
    def split_into_sections(data: bytes) -> list[bytes]:
        """Split bytes into list of fixed-length chunks."""
        return [
            data[i : i + IGF_SECT_DATA_LEN]
            for i in range(0, len(data), IGF_SECT_DATA_LEN)
        ]

    @staticmethod
    def get_payload_of(sections: DataModelCollection["Section"]) -> bytes:
        """Return bytes for all sections, excluding headers."""
        return b"".join(section.data for section in sections)
