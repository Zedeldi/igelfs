"""Abstract base classes to provide an interface for data models."""

from abc import ABC, abstractmethod
from pathlib import Path


class BaseBytesModel(ABC):
    """Abstract base class for handling bytes."""

    @abstractmethod
    def to_bytes(self) -> bytes:
        """Return bytes of all data."""
        ...

    def write(self, path: str | Path) -> Path:
        """Write data of model to specified path and return Path object."""
        path = Path(path).absolute()
        with open(path, "wb") as fd:
            fd.write(self.to_bytes())
        return path

    def get_actual_size(self) -> int:
        """Return actual size of all data."""
        return len(self.to_bytes())

    def get_offset_of(self, data: bytes) -> int:
        """Return offset of model instance for start of data."""
        return self.to_bytes().index(data)

    def get_offset_relative_to(self, data: bytes) -> int:
        """Return offset of data for start of model instance."""
        return data.index(self.to_bytes())