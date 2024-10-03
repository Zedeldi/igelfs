"""Mixin classes to extend functionality for various data models."""

import zlib
from typing import ClassVar


class CRCMixin:
    """Provide methods to handle CRC checking."""

    CRC_OFFSET: ClassVar[int]

    def get_crc(self) -> int:
        """Calculate CRC32 of section."""
        return zlib.crc32(self.to_bytes()[self.CRC_OFFSET :])
