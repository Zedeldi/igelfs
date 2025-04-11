"""Concrete base classes for various data models."""

import io
import logging
from collections.abc import Iterator, Mapping
from dataclasses import Field, dataclass
from typing import Any, get_args, get_origin

from igelfs.models.abc import BaseBytesModel
from igelfs.models.collections import DataModelCollection
from igelfs.models.mixins import DataclassMixin
from igelfs.utils import replace_bytes

logger = logging.getLogger(__name__)


@dataclass
class DataModelMetadata(Mapping, DataclassMixin):
    """
    Dataclass to provide metadata for data models.

    The metadata for fields must be a mapping. This dataclass is used
    to provide a specification for attribute names instead of a dictionary.
    """

    size: int
    default: Any = None

    def __getitem__(self, key: str) -> Any:
        """Implement get item method for metadata."""
        return self.to_dict(shallow=True)[key]

    def __iter__(self) -> Iterator[str]:
        """Implement iterating through metadata."""
        yield from self.to_dict(shallow=True)

    def __len__(self) -> int:
        """Implement getting length of metadata."""
        return len(self.to_dict(shallow=True))


@dataclass
class BaseDataModel[T: BaseDataModel](BaseBytesModel, DataclassMixin):
    """Concrete base class for data model."""

    def __len__(self) -> int:
        """Implement __len__ data model method."""
        return self.get_actual_size()

    def to_bytes(self) -> bytes:
        """Return bytes of all data."""
        with io.BytesIO() as fd:
            for field in self.get_fields(init_only=False):
                data = getattr(self, field.name)
                try:
                    try:
                        size = self.get_attribute_size(field.name)
                    except KeyError:
                        size = 1
                    fd.write(self.convert_to_bytes(data, size))
                except TypeError:
                    continue
            fd.seek(0)
            return fd.read()

    @classmethod
    def _get_attribute_metadata(
        cls: type["BaseDataModel"],
    ) -> dict[str, Mapping[str, Any]]:
        """Return dictionary of attribute metadata."""
        return {field.name: field.metadata for field in cls.get_fields(init_only=True)}

    @classmethod
    def _get_attribute_metadata_by_name(
        cls: type["BaseDataModel"], name: str
    ) -> Mapping[str, Any]:
        """Return metadata for specified attribute."""
        return cls._get_attribute_metadata()[name]

    @classmethod
    def get_model_size(cls: type["BaseDataModel"]) -> int:
        """Return expected total size of data for model."""
        return sum(
            metadata["size"] for metadata in cls._get_attribute_metadata().values()
        )

    @classmethod
    def get_attribute_size(cls: type["BaseDataModel"], name: str) -> int:
        """Return size of data for attribute."""
        return cls._get_attribute_metadata_by_name(name)["size"]

    @classmethod
    def get_attribute_offset(cls: type["BaseDataModel"], name: str) -> int:
        """Return offset of bytes for attribute."""
        offset = 0
        for attribute, metadata in cls._get_attribute_metadata().items():
            if attribute == name:
                return offset
            offset += metadata["size"]
        else:
            raise KeyError(f"Attribute '{name}' not found")

    def verify(self) -> bool:
        """Verify data model integrity."""
        result = self.get_actual_size() == self.get_model_size()
        try:
            result = result and super().verify()  # type: ignore[misc]
        except AttributeError:
            pass
        return result

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
            for field in cls.get_fields(init_only=True):
                data = fd.read(cls.get_attribute_size(field.name))
                if not data:
                    raise ValueError(f"Not enough data for model '{cls.__name__}'")
                model[field.name] = data
        return model

    @staticmethod
    def from_field(data: bytes, field: Field) -> Any:
        """Return instance of field type from data."""
        if isinstance(field.type, str):
            raise TypeError(f"Type of field '{field.type}' must be a class")
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
    def from_bytes(cls: type[T], data: bytes) -> T:
        """Return data model instance from bytes."""
        logger.debug(f"Creating model {cls.__name__} from {len(data)} bytes")
        model = cls.from_bytes_to_dict(data)
        for field in cls.get_fields(init_only=True):
            model[field.name] = cls.from_field(model[field.name], field)
        return cls(**model)

    @classmethod
    def from_bytes_with_remaining(cls: type[T], data: bytes) -> tuple[T, bytes]:
        """Return data model instance and remaining data from bytes."""
        return (cls.from_bytes(data), data[cls.get_model_size() :])

    @classmethod
    def from_bytes_to_generator(
        cls: type[T], data: bytes, limit: int | None = None
    ) -> Iterator[T]:
        """Return generator of data models from bytes."""
        n = 0
        while data and (not limit or n < limit):
            model, data = cls.from_bytes_with_remaining(data)
            n += 1
            yield model

    @classmethod
    def from_bytes_to_collection(
        cls: type[T], data: bytes, limit: int | None = None
    ) -> DataModelCollection[T]:
        """Return collection of data models from bytes."""
        return DataModelCollection(cls.from_bytes_to_generator(data, limit=limit))

    @classmethod
    def _get_default_bytes(cls: type["BaseDataModel"]) -> bytes:
        """Return default bytes for new data model."""
        data = bytes(cls.get_model_size())
        for name, metadata in cls._get_attribute_metadata().items():
            value = metadata.get("default")
            if not value:
                continue
            if callable(value):
                value = value()
            offset = cls.get_attribute_offset(name)
            try:
                size = cls.get_attribute_size(name)
            except KeyError:
                size = 1
            data = replace_bytes(data, cls.convert_to_bytes(value, size), offset)
        return data

    @classmethod
    def new(cls: type[T], **kwargs) -> T:
        """Return new data model instance with default data."""
        model = cls.from_bytes(cls._get_default_bytes())
        for name, value in kwargs.items():
            try:
                cls.get_field_by_name(name, init_only=False)
            except ValueError as error:
                raise ValueError(
                    f"Cannot instantiate model '{cls.__name__}' with field '{name}'"
                ) from error
            try:
                if len(value) != cls.get_attribute_size(name):
                    raise ValueError(f"Incorrect size for attribute '{name}'")
            except TypeError:
                # value does not have a length implementation
                pass
            setattr(model, name, value)
        return model


class BaseDataGroup(BaseBytesModel, DataclassMixin):
    """Concrete base class for a dataclass of data models."""

    def to_bytes(self) -> bytes:
        """Return bytes of all data."""
        with io.BytesIO() as fd:
            for field in self.get_fields(init_only=False):
                data = getattr(self, field.name)
                try:
                    fd.write(self.convert_to_bytes(data))
                except TypeError:
                    continue
            fd.seek(0)
            return fd.read()
