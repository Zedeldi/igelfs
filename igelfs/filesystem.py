"""Python implementation to handle IGEL filesystems."""

from pathlib import Path

from igelfs.constants import (
    DIR_OFFSET,
    DIR_SIZE,
    IGEL_BOOTREG_OFFSET,
    IGEL_BOOTREG_SIZE,
    IGF_SECTION_SIZE,
    SectionSize,
    get_start_of_section,
)
from igelfs.models import BootRegistryHeader, Directory, Section


class Filesystem:
    """IGEL filesystem class to handle properties and methods."""

    def __init__(self, path: str | Path) -> None:
        """Initialise instance."""
        self.path = Path(path).absolute()

    def __getitem__(self, index: int) -> Section:
        """Implement getitem method."""
        return self.get_section_by_index(index)

    @property
    def size(self) -> int:
        """Return size of image."""
        return self.path.stat().st_size

    @property
    def section_size(self) -> SectionSize:
        """Return SectionSize for image."""
        return SectionSize.get(self.size)

    @property
    def bootreg(self) -> BootRegistryHeader:
        """Return Boot Registry Header for image."""
        data = self.get_data(IGEL_BOOTREG_OFFSET, IGEL_BOOTREG_SIZE)
        return BootRegistryHeader.from_bytes(data)

    @property
    def directory(self) -> Directory:
        """Return Directory for image."""
        data = self.get_data(DIR_OFFSET, DIR_SIZE)
        return Directory.from_bytes(data)

    def get_data(self, offset: int = 0, size: int = -1):
        """Return data for specified offset and size."""
        if offset > self.size:
            raise ValueError("Offset is greater than image size.")
        with open(self.path, "rb") as fd:
            fd.seek(offset)
            return fd.read(size)

    def get_section_by_offset(self, offset: int, size: int) -> Section:
        """Return Section of image by offset and size."""
        data = self.get_data(offset, size)
        return Section.from_bytes(data)

    def get_section_by_index(self, index: int) -> Section:
        """Return Section of image by index."""
        offset = get_start_of_section(index)
        data = self.get_data(offset, IGF_SECTION_SIZE)
        return Section.from_bytes(data)
