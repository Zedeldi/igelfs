"""Data models for the boot registry of a filesystem image."""

from abc import abstractmethod
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from typing import ClassVar

from igelfs.constants import BOOTREG_IDENT, BOOTREG_MAGIC, IGEL_BOOTREG_SIZE
from igelfs.models.base import BaseDataModel, DataModelMetadata
from igelfs.models.collections import DataModelCollection


def generate_boot_id() -> str:
    """Generate a boot ID based on current date."""
    dt = datetime.now()
    return dt.strftime("%y%m%d%H%M%S") + dt.strftime("%f").zfill(9)


@dataclass
class BootRegistryEntry(BaseDataModel):
    """Dataclass to describe each entry of boot registry."""

    # 16 bits: 9 bits next index, 1 bit next present, 6 bit key length
    flag: int = field(metadata=DataModelMetadata(size=2))
    data: bytes = field(metadata=DataModelMetadata(size=62))

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
                    self.flag.to_bytes(self.get_attribute_size("flag"), "big").hex(),
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
        next_block_index, next_block_present, key_length = map(
            partial(int, base=2), self._flag_bits
        )
        return (next_block_index, next_block_present, key_length)

    @classmethod
    def get_flag_from_values(
        cls: type["BootRegistryEntry"],
        next_block_index: int,
        next_block_present: bool,
        key_length: int,
    ) -> int:
        """Return flag integer for specified values."""
        next_block_index_bits = bin(next_block_index).removeprefix("0b").zfill(9)
        next_block_present_bit = int(next_block_present)
        key_length_bits = bin(key_length).removeprefix("0b").zfill(6)
        return int(
            f"{next_block_index_bits}{next_block_present_bit}{key_length_bits}", 2
        )

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

    @value.setter
    def value(self, value: str) -> None:
        """Set value for boot registry entry."""
        self.data = f"{self.key}{value}".encode().ljust(
            self.get_attribute_size("data"), b"\x00"
        )


@dataclass
class BaseBootRegistryHeader(BaseDataModel):
    """Base class for boot registry header."""

    STRUCTURE: ClassVar[str]

    ident_legacy: str = field(  # "IGEL BOOTREGISTRY"
        metadata=DataModelMetadata(size=17, default=BOOTREG_IDENT)
    )

    def __post_init__(self) -> None:
        """Verify identity string on initialisation."""
        if self.ident_legacy != BOOTREG_IDENT:
            raise ValueError(
                f"Unexpected identity string '{self.ident_legacy}' for boot registry"
            )

    def get_type(self) -> str:
        """Return type of boot registry as string."""
        return self.STRUCTURE

    @abstractmethod
    def get_boot_id(self) -> str:
        """Return boot ID from boot registry."""
        ...

    @abstractmethod
    def get_entries(self) -> dict[str, str]:
        """Return dictionary of all boot registry entries."""
        ...

    @abstractmethod
    def set_entry(self, key: str, value: str) -> None:
        """Set entry of boot registry."""
        ...


@dataclass
class BootRegistryHeader(BaseBootRegistryHeader):
    """
    Dataclass to handle boot registry header data.

    The boot registry resides in section #0 of the image.
    """

    STRUCTURE: ClassVar[str] = "structured"

    magic: str = field(  # BOOTREG_MAGIC
        metadata=DataModelMetadata(size=4, default=BOOTREG_MAGIC)
    )
    hdr_version: int = field(  # 0x01 for the first
        metadata=DataModelMetadata(size=1, default=1)
    )
    boot_id: str = field(metadata=DataModelMetadata(size=21, default=generate_boot_id))
    enc_alg: int = field(metadata=DataModelMetadata(size=1))  # encryption algorithm
    flags: int = field(metadata=DataModelMetadata(size=2))  # flags
    empty: bytes = field(metadata=DataModelMetadata(size=82))  # placeholder
    free: bytes = field(  # bitmap with free 64 byte blocks
        metadata=DataModelMetadata(size=64)
    )
    used: bytes = field(  # bitmap with used 64 byte blocks
        metadata=DataModelMetadata(size=64)
    )
    dir: bytes = field(  # directory bitmap (4 bits for each block -> key length)
        metadata=DataModelMetadata(size=252)
    )
    reserve: bytes = field(metadata=DataModelMetadata(size=4))  # placeholder
    entry: DataModelCollection[BootRegistryEntry] = field(  # actual entries
        metadata=DataModelMetadata(size=504 * BootRegistryEntry.get_model_size())
    )

    def __post_init__(self) -> None:
        """Verify magic string on initialisation."""
        super().__post_init__()
        if self.magic != BOOTREG_MAGIC:
            raise ValueError(
                f"Unexpected magic string '{self.magic}' for boot registry"
            )

    def _get_entries_for_key(self, key: str) -> DataModelCollection[BootRegistryEntry]:
        """Return collection of all entries for key."""
        entries: DataModelCollection[BootRegistryEntry] = DataModelCollection()
        for entry in self.entry:
            if not entry.value:
                continue
            if entry.key == key:
                entries.append(entry)
                while entry.next_block_present:
                    entry = self.entry[entry.next_block_index]
                    entries.append(entry)
                break
        return entries

    @property
    def _entry_keys(self) -> Iterator[str]:
        """Return iterator of keys for all entries."""
        for entry in self.entry:
            if not entry.key:
                continue
            yield entry.key

    def get_boot_id(self) -> str:
        """Return boot ID from boot registry."""
        return self.boot_id

    def get_entries(self) -> dict[str, str]:
        """Return dictionary of all boot registry entries."""
        entries = {}
        for key in self._entry_keys:
            entries[key] = "".join(
                [entry.value for entry in self._get_entries_for_key(key)]
            )
        return entries

    def _get_next_entry_index(self, exclude: Iterable[int] | None = None) -> int:
        """Return next index for free entry."""
        for index, entry in enumerate(self.entry):
            if exclude and index in exclude:
                continue
            if not entry.value:
                return index
        else:
            raise ValueError("No free entry found")

    def _new_entry(self, key: str, value: str) -> dict[int, BootRegistryEntry]:
        """Create and return dictionary of indexes to entries for given values."""
        entries = {}
        next_block_index = 0
        exclude = []
        while value:
            key_length = len(key)
            index = next_block_index or self._get_next_entry_index()
            exclude.append(index)
            limit = BootRegistryEntry.get_attribute_size("data") - key_length
            if limit < len(value):  # value spans multiple entries
                next_block_index = self._get_next_entry_index(exclude=exclude)
                next_block_present = True
            else:
                next_block_index = 0
                next_block_present = False
            flag = BootRegistryEntry.get_flag_from_values(
                next_block_index, next_block_present, key_length
            )
            data = f"{key}{value[:limit]}".encode().ljust(
                BootRegistryEntry.get_attribute_size("data"), b"\x00"
            )
            entry = BootRegistryEntry.new(flag=flag, data=data)
            entries[index] = entry
            value = value[limit:]
            key = ""
        return entries

    def set_entry(self, key: str, value: str) -> None:
        """Set entry of boot registry."""
        entries = self._get_entries_for_key(key)
        for entry in entries:
            # must preserve index of all entries for next_block_index
            # do not remove entries - just replace with an empty one
            index = self.entry.index(entry)
            self.entry[index] = BootRegistryEntry.new()
        for index, entry in self._new_entry(key, value).items():
            self.entry[index] = entry
        return None


@dataclass
class BootRegistryHeaderLegacy(BaseBootRegistryHeader):
    """
    Dataclass to handle legacy boot registry header data.

    The boot registry resides in section #0 of the image.
    """

    STRUCTURE: ClassVar[str] = "legacy"
    BOOT_ID_KEY: ClassVar[str] = "boot_id"
    EOF: ClassVar[str] = "EOF"

    entry: bytes = field(metadata=DataModelMetadata(size=IGEL_BOOTREG_SIZE - 17))

    @classmethod
    def _convert_entries_from_dict_to_bytes(
        cls: type["BootRegistryHeaderLegacy"], entries: dict[str, str], pad: bool = True
    ) -> bytes:
        """Convert dictionary of entries to bytes."""
        content = "\n".join(f"{key}={value}" for key, value in entries.items())
        data = f"\n{content}\n{cls.EOF}\n".encode()
        if pad:
            data = data.ljust(cls.get_attribute_size("entry"), b"\x00")
        return data

    def get_boot_id(self) -> str:
        """Return boot ID from boot registry."""
        return self.get_entries()[self.BOOT_ID_KEY]

    def get_entries(self) -> dict[str, str]:
        """Return dictionary of all boot registry entries."""
        entries = {}
        for entry in self.entry.decode().splitlines():
            if not entry:
                continue
            if entry == self.EOF:
                break
            try:
                key, value = entry.split("=")
            except ValueError:
                continue
            entries[key] = value
        return entries

    def set_entry(self, key: str, value: str) -> None:
        """Set entry of boot registry."""
        entries = self.get_entries()
        entries[key] = value
        self.entry = self._convert_entries_from_dict_to_bytes(entries)


class BootRegistryHeaderFactory:
    """Class to handle returning the correct boot registry header model."""

    @staticmethod
    def is_legacy_boot_registry(data: bytes) -> bool:
        """Return whether bytes represent a legacy boot registry header."""
        ident_legacy = BootRegistryHeader.get_attribute_size("ident_legacy")
        magic = BootRegistryHeader.get_attribute_size("magic")
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
