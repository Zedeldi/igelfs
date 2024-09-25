"""Abstract base classes for various data models."""

import io
import zlib
from abc import ABC
from dataclasses import Field, dataclass, fields
from pathlib import Path
from typing import Any, ClassVar, get_args, get_origin


@dataclass
class BaseDataModel(ABC):
    """Abstract base class for data model."""

    MODEL_ATTRIBUTE_SIZES: ClassVar[dict[str, int]]
    CRC_OFFSET: ClassVar[int]

    def __len__(self) -> int:
        """Implement __len__ data model method."""
        return self.get_actual_size()

    def to_bytes(self) -> bytes:
        """Return bytes of all data."""
        with io.BytesIO() as fd:
            for attribute, size in self.MODEL_ATTRIBUTE_SIZES.items():
                data = getattr(self, attribute)
                match data:
                    case bytes():
                        fd.write(data)
                    case int():
                        fd.write(data.to_bytes(size))
                    case str():
                        fd.write(data.encode())
                    case BaseDataModel() | DataModelCollection():
                        fd.write(data.to_bytes())
            fd.seek(0)
            return fd.read()

    def write(self, path: str | Path) -> Path:
        """Write data of model to specified path and return Path object."""
        path = Path(path).absolute()
        with open(path, "wb") as fd:
            fd.write(self.to_bytes())
        return path

    def get_actual_size(self) -> int:
        """Return actual size of all data."""
        return len(self.to_bytes())

    @classmethod
    def get_model_size(cls: type["BaseDataModel"]) -> int:
        """Return expected total size of data for model."""
        return sum(cls.MODEL_ATTRIBUTE_SIZES.values())

    def get_crc(self) -> int:
        """Calculate CRC32 of section."""
        if not getattr(self, "CRC_OFFSET"):
            raise NotImplementedError("Model has not implemented CRC32 method.")
        return int.from_bytes(
            zlib.crc32(self.to_bytes()[self.CRC_OFFSET :]).to_bytes(4, "little")
        )

    def verify(self) -> bool:
        """Verify data model integrity."""
        try:
            return self.crc == self.get_crc()
        except AttributeError:
            return self.get_actual_size() == self.get_model_size()

    @classmethod
    def from_bytes_to_dict(cls: type["BaseDataModel"], data: bytes) -> dict[str, bytes]:
        """Return dictionary from bytes."""
        model = {}
        with io.BytesIO(data) as fd:
            for attribute, size in cls.MODEL_ATTRIBUTE_SIZES.items():
                model[attribute] = fd.read(size)
        return model

    @staticmethod
    def from_field(data: bytes, field: Field) -> Any:
        """Return instance of field type from data."""
        if get_origin(field.type) == DataModelCollection:
            inner = get_args(field.type)[0]
            return DataModelCollection(
                inner.from_bytes(chunk)
                for chunk in [
                    data[i : i + inner.get_model_size()]
                    for i in range(0, len(data), inner.get_model_size())
                ]
            )
        elif issubclass(field.type, BaseDataModel):
            return field.type.from_bytes(data)
        elif field.type == str:
            return data.decode()
        elif field.type == int:
            return int.from_bytes(data)
        else:
            return field.type(data)

    @classmethod
    def from_bytes(cls: type["BaseDataModel"], data: bytes) -> "BaseDataModel":
        """Return data model instance from bytes."""
        model = cls.from_bytes_to_dict(data)
        for field in fields(cls):
            model[field.name] = cls.from_field(model[field.name], field)
        return cls(**model)


class DataModelCollection(list):
    """List subclass to provide additional helper methods."""

    def to_bytes(self) -> bytes:
        """Return bytes of all models."""
        with io.BytesIO() as fd:
            for model in self:
                fd.write(model.to_bytes())
            fd.seek(0)
            return fd.read()

    @property
    def size(self) -> int:
        """Return actual size of all data."""
        return len(self.to_bytes())
