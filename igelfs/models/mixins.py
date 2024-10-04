"""Mixin classes to extend functionality for various data models."""

import zlib
from typing import ClassVar


class CRCMixin:
    """Provide methods to handle CRC checking."""

    CRC_OFFSET: ClassVar[int]
    crc: int

    def get_crc(self) -> int:
        """Calculate CRC32 of section."""
        return zlib.crc32(self.to_bytes()[self.CRC_OFFSET :])

    def verify(self) -> bool:
        """Verify CRC32 checksum."""
        return self.crc == self.get_crc()
