"""Collection of functions to assist other modules."""

import abc
import contextlib
import io
import subprocess
import tarfile
import tempfile
from collections.abc import Generator
from types import TracebackType
from typing import Any

from igelfs.constants import IGF_SECTION_SHIFT, IGF_SECTION_SIZE


def get_start_of_section(index: int) -> int:
    """Return offset for start of section relative to image."""
    return index << IGF_SECTION_SHIFT


def get_section_of(offset: int) -> int:
    """Return section index for specified offset."""
    return offset >> IGF_SECTION_SHIFT


def get_offset_of(offset: int) -> int:
    """Return offset relative to start of section for specified offset."""
    return offset & (IGF_SECTION_SIZE - 1)


def replace_bytes(
    data: bytes, replacement: bytes, offset: int, strict: bool = True
) -> bytes:
    """
    Replace bytes at offset in data with replacement.

    If strict is True, ensure replacement will fit inside data.
    """
    if strict and len(replacement) > len(data) - offset:
        raise ValueError("Replacement does not fit inside data")
    with io.BytesIO(data) as fd:
        fd.seek(offset)
        fd.write(replacement)
        fd.seek(0)
        return fd.read()


def run_process(*args, **kwargs) -> str:
    """Run process and return stdout or raise exception if failed."""
    return (
        subprocess.run(
            *args,
            capture_output=kwargs.pop("capture_output", True),
            check=kwargs.pop("check", True),
            **kwargs,
        )
        .stdout.strip()
        .decode()
    )


@contextlib.contextmanager
def tarfile_from_bytes(data: bytes) -> Generator[tarfile.TarFile]:
    """Context manager for creating a TarFile from bytes."""
    with io.BytesIO(data) as file:
        with tarfile.open(fileobj=file) as tar:
            yield tar


@contextlib.contextmanager
def tempfile_from_bytes(data: bytes) -> Generator[str]:
    """Write bytes to temporary file and return path."""
    with tempfile.NamedTemporaryFile(delete_on_close=False) as file:
        file.write(data)
        file.close()
        yield file.name


class BaseContext(contextlib.AbstractContextManager):
    """Base class for helper context managers."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialise instance with passed arguments."""
        self._args = args
        self._kwargs = kwargs

    def __enter__(self) -> Any:
        """Enter runtime context for object."""
        self._context = self.context(*self._args, **self._kwargs)
        return self._context.__enter__()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        """Exit runtime context for object."""
        return self._context.__exit__(exc_type, exc_value, traceback)

    @classmethod
    @contextlib.contextmanager
    @abc.abstractmethod
    def context(cls: type["BaseContext"], *args, **kwargs) -> Generator[Any]:
        """Abstract class method allowing helper classes to be used as context managers."""
        ...
