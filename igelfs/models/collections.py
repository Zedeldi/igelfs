"""Helper classes to provide represent collections of data models."""

import io


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
