"""Data models for a section."""

import io
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
from igelfs.models.hash import Hash, HashExclude, HashHeader
from igelfs.models.mixins import CRCMixin
from igelfs.models.partition import Partition, PartitionExtent, PartitionHeader
from igelfs.utils import get_start_of_section


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
class Section(BaseDataModel, CRCMixin):
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
    partition: Partition | None = field(init=False)
    hash: Hash | None = field(init=False)
    data: bytes

    def __post_init__(self) -> None:
        """Parse data into optional additional attributes."""
        # Partition
        try:  # Partition header
            partition_header, self.data = PartitionHeader.from_bytes_with_remaining(
                self.data
            )
        except ValueError:
            self.partition = None
        else:  # Partition extents
            partition_extents = DataModelCollection()
            for _ in range(partition_header.n_extents):
                extent, self.data = PartitionExtent.from_bytes_with_remaining(self.data)
                partition_extents.append(extent)
            self.partition = Partition(
                header=partition_header, extents=partition_extents
            )

        # Hashing
        try:  # Hash header
            hash_header, self.data = HashHeader.from_bytes_with_remaining(self.data)
        except (UnicodeDecodeError, ValueError):
            self.hash = None
        else:  # Hash excludes
            hash_excludes = DataModelCollection()
            for _ in range(hash_header.count_excludes):
                hash_exclude, self.data = HashExclude.from_bytes_with_remaining(
                    self.data
                )
                hash_excludes.append(hash_exclude)
            hash_values, self.data = (
                self.data[: hash_header.hash_block_size],
                self.data[hash_header.hash_block_size :],
            )
            self.hash = Hash(
                header=hash_header, excludes=hash_excludes, values=hash_values
            )

    @property
    def crc(self) -> int:
        """Return CRC32 checksum from header."""
        return self.header.crc

    @property
    def end_of_chain(self) -> bool:
        """Return whether this section is the last in the chain."""
        return self.header.next_section == 0xFFFFFFFF

    def _to_bytes_excluding_by_indices(self, hash_: Hash) -> bytes:
        """
        Return bytes of section excluding specified indices.

        Excluded bytes are replaced with 0x00.
        """
        excludes = HashExclude.get_excluded_indices_from_collection(hash_.excludes)
        offset = get_start_of_section(self.header.section_in_minor)
        with io.BytesIO() as fd:
            for index, byte in enumerate([bytes([i]) for i in self.to_bytes()]):
                if index + offset in excludes:
                    fd.write(b"\x00")
                    continue
                fd.write(byte)
            fd.seek(0)
            return fd.read()

    def _to_bytes_excluding_by_range(self, hash_: Hash) -> bytes:
        """
        Return bytes of section excluding specified ranges.

        Excluded bytes are replaced with 0x00.
        This is a port of the original generate_hash method from validate.c.
        """
        position = self.header.section_in_minor * hash_.header.blocksize
        with io.BytesIO(self.to_bytes()) as fd:
            for exclude in hash_.excludes:
                if (
                    exclude.start >= position
                    and exclude.start < position + hash_.header.blocksize
                ):
                    fd.seek(exclude.start)
                    fd.write(b"\x00" * exclude.size)
                    continue
                if not exclude.repeat or exclude.end < position:
                    continue
                repeat = (position / exclude.repeat) * exclude.repeat + exclude.start
                if repeat <= position and repeat + exclude.size > position:
                    size = int((repeat + exclude.size) - position)
                    fd.write(b"\x00" * size)
                    continue
                if repeat >= position and repeat < position + hash_.header.blocksize:
                    fd.seek(int(repeat - position))
                    fd.write(b"\x00" * exclude.size)
                    continue
            fd.seek(0)
            return fd.read()

    def calculate_hash(self, hash_: Hash) -> bytes:
        """Return hash of section excluding specified ranges."""
        data = self._to_bytes_excluding_by_range(hash_)
        return hash_.calculate_hash(data)

    @staticmethod
    def split_into_sections(data: bytes) -> list[bytes]:
        """Split bytes into list of fixed-length chunks."""
        return [
            data[i : i + IGF_SECT_DATA_LEN]
            for i in range(0, len(data), IGF_SECT_DATA_LEN)
        ]

    @staticmethod
    def get_payload_of(
        sections: DataModelCollection["Section"], include_extents: bool = False
    ) -> bytes:
        """Return bytes for all sections, excluding headers."""
        data = b"".join(section.data for section in sections)
        if not include_extents:
            data = data[sections[0].partition.get_extents_length() :]
        return data

    @classmethod
    def get_extent_of(
        cls: type["Section"],
        sections: DataModelCollection["Section"],
        extent: PartitionExtent,
    ) -> bytes:
        """Return bytes for extent of sections."""
        offset = extent.offset
        if partition := sections[0].partition:
            offset -= partition.get_actual_size()
        if hash_ := sections[0].hash:
            offset -= hash_.get_actual_size()
        data = cls.get_payload_of(sections, include_extents=True)
        return data[offset : offset + extent.length]
