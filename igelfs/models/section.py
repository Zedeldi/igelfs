"""Data models for a section."""

import copy
import io
from dataclasses import dataclass, field
from typing import Any

import magic

from igelfs.constants import (
    IGF_SECT_DATA_LEN,
    IGF_SECT_HDR_LEN,
    IGF_SECT_HDR_MAGIC,
    SECTION_END_OF_CHAIN,
    SECTION_IMAGE_CRC_START,
)
from igelfs.models.base import BaseDataModel, DataModelMetadata
from igelfs.models.collections import DataModelCollection
from igelfs.models.hash import Hash, HashExclude, HashHeader
from igelfs.models.mixins import CRCMixin
from igelfs.models.partition import Partition, PartitionExtent, PartitionHeader
from igelfs.utils import get_start_of_section


@dataclass
class SectionHeader(BaseDataModel):
    """Dataclass to handle section header data."""

    crc: int = field(  # crc of the rest of the section
        metadata=DataModelMetadata(size=4)
    )
    magic: int = field(  # magic number (erase count long ago)
        metadata=DataModelMetadata(size=4, default=IGF_SECT_HDR_MAGIC[-1])
    )
    section_type: int = field(metadata=DataModelMetadata(size=2, default=1))
    section_size: int = field(  # log2((section size in bytes) / 65536)
        metadata=DataModelMetadata(size=2, default=2)
    )
    partition_minor: int = field(  # partition number (driver minor number)
        metadata=DataModelMetadata(size=4)
    )
    generation: int = field(  # update generation count
        metadata=DataModelMetadata(size=2, default=1)
    )
    section_in_minor: int = field(  # n = 0,...,(number of sect.-1)
        metadata=DataModelMetadata(size=4)
    )
    next_section: int = field(  # index of the next section or 0xffffffff = end of chain
        metadata=DataModelMetadata(size=4)
    )
    reserved: bytes = field(  # section header is 32 bytes but 6 bytes are unused
        metadata=DataModelMetadata(size=6)
    )

    def __post_init__(self) -> None:
        """Verify magic number on initialisation."""
        if self.magic not in IGF_SECT_HDR_MAGIC:
            raise ValueError(f"Unexpected magic '{self.magic}' for section header")


@dataclass
class Section(BaseDataModel, CRCMixin):
    """
    Dataclass to handle section of an image.

    Not all sections have a partition or hash header. Data is parsed
    post-initialisation to add these attributes.
    """

    CRC_OFFSET = SECTION_IMAGE_CRC_START

    header: SectionHeader = field(
        metadata=DataModelMetadata(size=IGF_SECT_HDR_LEN, default=SectionHeader.new())
    )
    partition: Partition | None = field(init=False)
    hash: Hash | None = field(init=False)
    data: bytes = field(metadata=DataModelMetadata(size=IGF_SECT_DATA_LEN))

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
            partition_extents: DataModelCollection[PartitionExtent] = (
                DataModelCollection()
            )
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
            hash_excludes: DataModelCollection[HashExclude] = DataModelCollection()
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

    @crc.setter
    def crc(self, value: int):
        """Set CRC32 checksum in header to value."""
        self.header.crc = value

    @property
    def end_of_chain(self) -> bool:
        """Return whether this section is the last in the chain."""
        return self.header.next_section == SECTION_END_OF_CHAIN

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

    def calculate_hash(self, hash_: Hash, section_in_minor: int | None = None) -> bytes:
        """
        Return hash of section excluding specified ranges.

        Due to an issue with the igelupdate utility up to (but not including)
        version 11.02.100, the current partition minor is written into the
        section_in_minor field, instead of keeping the strictly increasing
        counter (which is in there during signage).

        To resolve this issue, manually specify the section_in_minor to
        change this value before calculating the hash.
        """
        if section_in_minor is not None:
            # Create a copy of the section instance
            section = Section.from_bytes(self.to_bytes())
            section.header.section_in_minor = section_in_minor
            data = section._to_bytes_excluding_by_range(hash_)
        else:
            data = self._to_bytes_excluding_by_range(hash_)
        return hash_.calculate_hash(data)

    @staticmethod
    def split_into_sections(data: bytes, pad: bool = False) -> list[bytes]:
        """
        Split bytes into list of fixed-length chunks.

        If pad is True, pad the last section with null bytes to fit length.
        """
        sections = [
            data[i : i + IGF_SECT_DATA_LEN]
            for i in range(0, len(data), IGF_SECT_DATA_LEN)
        ]
        if pad:
            sections[-1] = sections[-1].ljust(IGF_SECT_DATA_LEN, b"\x00")
        return sections

    def resize(self) -> None:
        """
        Resize payload of Section instance to correct size and update CRC.

        This will append null bytes or destructively truncate the payload.
        """
        payload_size = IGF_SECT_DATA_LEN
        if self.partition:
            payload_size -= self.partition.get_actual_size()
        if self.hash:
            payload_size -= self.hash.get_actual_size()
        if (difference := len(self.data) - payload_size) < 0:
            self.data += bytes(abs(difference))
        else:
            self.data = self.data[:payload_size]
        self.update_crc()

    def zero(self) -> None:
        """Set payload of Section instance to null bytes and update CRC."""
        self.data = b"\x00" * len(self.data)
        self.update_crc()

    @classmethod
    def set_payload_of(
        cls: type["Section"],
        sections: DataModelCollection["Section"],
        payload: bytes,
        preserve_extents: bool = True,
        zero: bool = True,
    ) -> DataModelCollection["Section"]:
        """
        Set payload for collection of sections to bytes in payload.

        If preserve_extents is True, extent payloads will not be overwritten.
        If zero is True, zero the payload of sections before replacing.
        """
        # Copy list of sections to prevent changing original data
        sections = copy.deepcopy(sections)
        if preserve_extents and (partition := sections[0].partition):
            for extent in sorted(
                partition.extents, key=lambda extent: extent.offset, reverse=True
            ):
                payload = Section.get_extent_of(sections, extent) + payload
        if hash_ := sections[0].hash:
            payload = hash_.to_bytes() + payload
            sections[0].hash = None
        if partition := sections[0].partition:
            payload = partition.to_bytes() + payload
            sections[0].partition = None
        data = cls.split_into_sections(payload, pad=True)
        if len(data) > len(sections):
            raise ValueError(
                f"Payload is too large to fit inside sections ({len(data)} > {len(sections)})"
            )
        if zero:
            for section in sections:
                section.zero()
        for index, section_bytes in enumerate(data):
            sections[index].data = section_bytes
            sections[index].update_crc()
        # Recreate section instance to re-add partition and hash attributes
        sections[0] = Section.from_bytes(sections[0].to_bytes())
        return sections

    @staticmethod
    def get_payload_of(
        sections: DataModelCollection["Section"], include_extents: bool = False
    ) -> bytes:
        """Return bytes for all sections, excluding headers."""
        data = b"".join(section.data for section in sections)
        if not include_extents and (partition := sections[0].partition):
            data = data[partition.get_extents_length() :]
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

    @classmethod
    def get_info_of(
        cls: type["Section"], sections: DataModelCollection["Section"]
    ) -> dict[str, Any]:
        """Return information for a collection of sections."""
        partition = sections[0].partition
        hash_ = sections[0].hash
        payload = cls.get_payload_of(sections)
        info: dict[str, Any] = {
            "section_count": len(sections),
            "size": sections.get_actual_size(),
            "payload": {
                "size": len(payload),
                "type": magic.from_buffer(payload),
                "mime": magic.from_buffer(payload, mime=True),
            },
            "verify": {
                "checksum": all(section.verify() for section in sections),
                "hash": None,
                "signature": None,
            },
            "name": None,
            "update_hash": None,
            "extents": [],
        }
        if hash_:
            info["verify"]["hash"] = all(
                section.calculate_hash(hash_, index) == hash_.get_hash(index)
                for index, section in enumerate(sections)
            )
            info["verify"]["signature"] = hash_.verify_signature()
        if partition:
            info["name"] = partition.header.get_name()
            info["update_hash"] = partition.header.update_hash.hex()
            for extent in partition.extents:
                extent_payload = cls.get_extent_of(sections, extent)
                extent_info = {
                    "name": extent.get_name(),
                    "type": magic.from_buffer(extent_payload),
                    "mime": magic.from_buffer(extent_payload, mime=True),
                    "size": len(extent_payload),
                }
                info["extents"].append(extent_info)
        return info
