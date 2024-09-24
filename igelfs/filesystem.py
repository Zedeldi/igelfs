"""Python implementation to handle IGEL filesystems."""

from dataclasses import dataclass
from pathlib import Path

from igelfs.constants import (
    DIR_OFFSET,
    DIR_SIZE,
    IGEL_BOOTREG_OFFSET,
    IGEL_BOOTREG_SIZE,
    IGF_SECT_DATA_LEN,
    IGF_SECT_HDR_LEN,
    IGF_SECTION_SIZE,
    SectionSize,
    get_section_of,
    get_start_of_section,
)
from igelfs.models import BootRegistryHeader, Directory, SectionHeader


@dataclass
class Section:
    """Dataclass to handle section of an image."""

    path: str | Path
    offset: int
    data: bytes
    index: int | None = None

    def __post_init__(self) -> None:
        """Handle post-initialisation of dataclass instance."""
        if self.index is None:
            self.index = get_section_of(self.offset)

    @property
    def size(self) -> int:
        """Return size of data."""
        return len(self.data)

    @property
    def header(self) -> bytes:
        """Return header of data."""
        return SectionHeader.from_bytes(self.data[:IGF_SECT_HDR_LEN])

    @property
    def payload(self) -> bytes:
        """Return header of data."""
        return self.data[IGF_SECT_HDR_LEN:IGF_SECT_DATA_LEN]

    def write(self, path: str | Path) -> Path:
        """Write data of section to specified path and return Path."""
        path = Path(path).absolute()
        with open(path, "wb") as fd:
            fd.write(self.data)
        return path


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
        """Return bootreg Section for image."""
        data = self.get_data(IGEL_BOOTREG_OFFSET, IGEL_BOOTREG_SIZE)
        return BootRegistryHeader.from_bytes(data)

    @property
    def directory(self) -> Directory:
        """Return directory Section for image."""
        data = self.get_data(DIR_OFFSET, DIR_SIZE)
        return Directory.from_bytes(data)

    def get_data(self, offset: int = 0, size: int = -1):
        """Return data for specified offset and size."""
        with open(self.path, "rb") as fd:
            fd.seek(offset)
            return fd.read(size)

    def get_section_by_offset(self, offset: int, size: int) -> Section:
        """Return section of image by offset and size."""
        data = self.get_data(offset, size)
        return Section(path=self.path, offset=offset, data=data)

    def get_section_by_index(self, index: int) -> Section:
        """Return section of image by index."""
        offset = get_start_of_section(index)
        data = self.get_data(offset, IGF_SECTION_SIZE)
        return Section(path=self.path, index=index, offset=offset, data=data)
