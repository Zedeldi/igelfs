"""Concrete base classes for various data models."""

import io
from dataclasses import Field, dataclass, fields
from typing import Any, ClassVar, Iterator, get_args, get_origin

from igelfs.models.abc import BaseBytesModel
from igelfs.models.collections import DataModelCollection


@dataclass
class BaseDataModel(BaseBytesModel):
    """Concrete base class for data model."""

    MODEL_ATTRIBUTE_SIZES: ClassVar[dict[str, int]]

    def __len__(self) -> int:
        """Implement __len__ data model method."""
        return self.get_actual_size()

    def to_bytes(self) -> bytes:
        """Return bytes of all data."""
        with io.BytesIO() as fd:
            for field in self.fields(init_only=False):
                data = getattr(self, field.name)
                match data:
                    case bytes():
                        fd.write(data)
                    case int():
                        size = self.get_attribute_size(field.name)
                        fd.write(data.to_bytes(size, byteorder="little"))
                    case str():
                        fd.write(data.encode())
                    case BaseBytesModel():
                        fd.write(data.to_bytes())
                    case _:
                        continue
            fd.seek(0)
            return fd.read()

    @classmethod
    def get_model_size(cls: type["BaseDataModel"]) -> int:
        """Return expected total size of data for model."""
        return sum(cls.MODEL_ATTRIBUTE_SIZES.values())

    @classmethod
    def get_attribute_size(cls: type["BaseDataModel"], name: str) -> int:
        """Return size of data for attribute."""
        return cls.MODEL_ATTRIBUTE_SIZES[name]

    def verify(self) -> bool:
        """Verify data model integrity."""
        return self.get_actual_size() == self.get_model_size()

    @classmethod
    def from_bytes_to_dict(
        cls: type["BaseDataModel"], data: bytes, strict: bool = False
    ) -> dict[str, bytes]:
        """
        Return dictionary from bytes.

        Raises a ValueError if data is too short to create model.

        If strict is True, raise ValueError if data length
        does not meet model size.
        """
        if strict and len(data) < cls.get_model_size():
            raise ValueError(
                f"Length of data '{len(data)}' "
                f"is shorter than model size '{cls.get_model_size()}'"
            )
        model = {}
        with io.BytesIO(data) as fd:
            for field in cls.fields(init_only=True):
                data = fd.read(cls.get_attribute_size(field.name))
                if not data:
                    raise ValueError(f"Not enough data for model '{cls.__name__}'")
                model[field.name] = data
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
            return int.from_bytes(data, byteorder="little")
        else:
            return field.type(data)

    @classmethod
    def from_bytes(cls: type["BaseDataModel"], data: bytes) -> "BaseDataModel":
        """Return data model instance from bytes."""
        model = cls.from_bytes_to_dict(data)
        for field in cls.fields(init_only=True):
            model[field.name] = cls.from_field(model[field.name], field)
        return cls(**model)

    @classmethod
    def from_bytes_with_remaining(
        cls: type["BaseDataModel"], data: bytes
    ) -> tuple["BaseDataModel", bytes]:
        """Return data model instance and remaining data from bytes."""
        return (cls.from_bytes(data), data[cls.get_model_size() :])

    @classmethod
    def fields(cls: type["BaseDataModel"], init_only: bool = True) -> Iterator[Field]:
        """
        Return iterator of fields for dataclass.

        If init_only, only include fields with parameters in __init__ method.
        """
        for field in fields(cls):
            if init_only and not field.init:
                continue
            yield field


class BaseDataGroup(BaseBytesModel):
    """Concrete base class for a dataclass of data models."""

    def to_bytes(self) -> bytes:
        """Return bytes of all data."""
        with io.BytesIO() as fd:
            for field in fields(self):
                data = getattr(self, field.name)
                match data:
                    case bytes():
                        fd.write(data)
                    case str():
                        fd.write(data.encode())
                    case BaseBytesModel():
                        fd.write(data.to_bytes())
                    case _:
                        continue
            fd.seek(0)
            return fd.read()
