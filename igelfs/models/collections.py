"""Helper classes to provide represent collections of data models."""

import io

from igelfs.models.abc import BaseBytesModel


class DataModelCollection[T: BaseBytesModel](BaseBytesModel, list[T]):
    """List subclass to provide additional helper methods."""

    def to_bytes(self) -> bytes:
        """Return bytes of all models."""
        with io.BytesIO() as fd:
            for model in self:
                fd.write(model.to_bytes())
            fd.seek(0)
            return fd.read()
