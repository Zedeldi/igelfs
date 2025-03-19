"""Mixin classes to extend functionality for various data models."""

import zlib
from collections.abc import Iterator
from dataclasses import Field, asdict, dataclass, fields
from typing import Any, ClassVar, Protocol


class BytesModelProtocol(Protocol):
    """Protocol to type for a base bytes model."""

    def to_bytes(self) -> bytes:
        """Stub method implemented in subclass."""
        ...


class Dataclass(Protocol):
    """Protocol to type for a dataclass."""

    __dataclass_fields__: ClassVar[dict[str, Any]]


class CRCMixin(BytesModelProtocol):
    """Provide methods to handle CRC checking."""

    CRC_OFFSET: ClassVar[int]
    crc: int

    def get_crc(self) -> int:
        """Calculate CRC32 of section."""
        return zlib.crc32(self.to_bytes()[self.CRC_OFFSET :])

    def verify(self) -> bool:
        """Verify CRC32 checksum."""
        return self.crc == self.get_crc()

    def update_crc(self) -> None:
        """Update CRC32 checksum to current value."""
        self.crc = self.get_crc()


@dataclass
class DataclassMixin:
    """Provide methods to obtain various data from a dataclass."""

    def to_dict(self, shallow: bool = False) -> dict[str, Any]:
        """
        Return dictionary for data model.

        If shallow is True, do not recurse into nested data structures.
        """
        if shallow:
            return {
                field.name: getattr(self, field.name)
                for field in self.get_fields(init_only=False)
            }
        return asdict(self)

    @classmethod
    def get_fields(cls: type[Dataclass], init_only: bool = True) -> Iterator[Field]:
        """
        Return iterator of fields for dataclass.

        If init_only, only include fields with parameters in __init__ method.
        """
        for field in fields(cls):
            if init_only and not field.init:
                continue
            yield field

    @classmethod
    def get_field_by_name(
        cls: type["DataclassMixin"], name: str, *args, **kwargs
    ) -> Field:
        """Return field for dataclass by name."""
        for field in cls.get_fields(*args, **kwargs):
            if field.name == name:
                return field
        else:
            raise ValueError(f"Field '{name}' not found")
