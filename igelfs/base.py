"""Abstract base classes for various data models."""

import io
from abc import ABC
from dataclasses import dataclass, fields
from typing import ClassVar, get_args, get_origin


@dataclass
class BaseDataModel(ABC):
    """Abstract base class for data model."""

    MODEL_ATTRIBUTE_SIZES: ClassVar[dict[str, int]]

    def __len__(self) -> int:
        """Implement __len__ data model method."""
        return self.size

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

    @property
    def size(self) -> int:
        """Return actual size of all data."""
        return len(self.to_bytes())

    @classmethod
    def get_model_size(cls) -> int:
        """Return expected total size of data for model."""
        return sum(cls.MODEL_ATTRIBUTE_SIZES.values())

    def verify(self) -> bool:
        """Verify data model integrity."""
        return self.size == self.get_model_size()

    @classmethod
    def from_bytes_to_dict(cls, data: bytes) -> dict[str, bytes]:
        """Return dictionary from bytes."""
        model = {}
        with io.BytesIO(data) as fd:
            for attribute, size in cls.MODEL_ATTRIBUTE_SIZES.items():
                model[attribute] = fd.read(size)
        return model

    @classmethod
    def from_bytes(cls, data: bytes) -> "BaseDataModel":
        """Return data model instance from bytes."""
        model = cls.from_bytes_to_dict(data)
        for field in fields(cls):
            if get_origin(field.type) == DataModelCollection:
                inner = get_args(field.type)[0]
                model[field.name] = DataModelCollection(
                    inner.from_bytes(chunk)
                    for chunk in [
                        model[field.name][i : i + inner.get_model_size()]
                        for i in range(
                            0, len(model[field.name]), inner.get_model_size()
                        )
                    ]
                )
            elif field.type == str:
                model[field.name] = model[field.name].decode()
            elif field.type == int:
                model[field.name] = int.from_bytes(model[field.name])
            else:
                model[field.name] = field.type(model[field.name])
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
