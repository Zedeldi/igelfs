"""Functions to handle device operations."""

import abc
import contextlib
import os
import re
import subprocess
import tempfile
import uuid
from collections.abc import Generator
from glob import glob
from types import TracebackType
from typing import Any

from igelfs.utils import run_process


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


class Cryptsetup(BaseContext):
    """Helper class for cryptsetup operations."""

    @staticmethod
    def is_luks(path: str | os.PathLike) -> bool:
        """Return whether path is a LUKS container."""
        try:
            run_process(["cryptsetup", "isLuks", path], check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    @staticmethod
    def open_luks(
        path: str | os.PathLike, name: str, keyfile: str | os.PathLike
    ) -> None:
        """Open LUKS container with specified name and keyfile."""
        run_process(
            [
                "cryptsetup",
                f"--master-key-file={keyfile}",
                "open",
                path,
                name,
            ]
        )

    @staticmethod
    def open_plain(
        path: str | os.PathLike, name: str, keyfile: str | os.PathLike
    ) -> None:
        """Open plain encrypted file at path with specified name and keyfile."""
        run_process(
            [
                "cryptsetup",
                "open",
                "--type=plain",
                "--cipher=aes-xts-plain64",
                "--key-size=512",
                f"--key-file={keyfile}",
                path,
                name,
            ]
        )

    @classmethod
    def open(
        cls: type["Cryptsetup"],
        path: str | os.PathLike,
        name: str,
        keyfile: str | os.PathLike,
    ) -> None:
        """Open encrypted file at path with specified name and keyfile."""
        if cls.is_luks(path):
            cls.open_luks(path, name, keyfile=keyfile)
        else:
            cls.open_plain(path, name, keyfile=keyfile)

    @staticmethod
    def close(name: str) -> None:
        """Close mapped device with name."""
        run_process(["cryptsetup", "close", name])

    @classmethod
    @contextlib.contextmanager
    def context(
        cls: type["Cryptsetup"],
        path: str | os.PathLike,
        keyfile: str | os.PathLike,
        name: str | None = None,
    ) -> Generator[str]:
        """Context manager to open path with specified name and keyfile, then close."""
        name = name or str(uuid.uuid4())
        cls.open(path, name, keyfile=keyfile)
        try:
            yield f"/dev/mapper/{name}"
        finally:
            cls.close(name)

    @classmethod
    def decrypt(
        cls: type["Cryptsetup"],
        path: str | os.PathLike,
        keyfile: str | os.PathLike,
    ) -> bytes:
        """Open encrypted file and return decrypted bytes."""
        with cls.context(path, keyfile=keyfile) as device:
            with open(device, "rb") as file:
                return file.read()


class Losetup(BaseContext):
    """Helper class for loop device operations."""

    @staticmethod
    def attach(path: str | os.PathLike) -> str:
        """Attach specified path as loop device, returning device path."""
        return run_process(["losetup", "--partscan", "--find", "--show", path])

    @staticmethod
    def detach(path: str | os.PathLike) -> None:
        """Detach specified loop device."""
        run_process(["losetup", "--detach", path])

    @classmethod
    @contextlib.contextmanager
    def context(cls: type["Losetup"], path: str | os.PathLike) -> Generator[str]:
        """Context manager to attach path as loop device, then detach on closing."""
        loop_device = cls.attach(path)
        try:
            yield loop_device
        finally:
            cls.detach(loop_device)


class Mount(BaseContext):
    """Helper class to mount device at mountpoint."""

    @staticmethod
    def mount(path: str | os.PathLike, mountpoint: str | os.PathLike) -> None:
        """Mount specified path at mountpoint."""
        run_process(["mount", path, mountpoint])

    @staticmethod
    def unmount(mountpoint: str | os.PathLike) -> None:
        """Unmount device mounted at mountpoint."""
        run_process(["umount", mountpoint])

    @classmethod
    @contextlib.contextmanager
    def context(
        cls: type["Mount"],
        path: str | os.PathLike,
        mountpoint: str | os.PathLike | None = None,
    ) -> Generator[str | os.PathLike]:
        """Context manager to attach path as loop device, then detach on closing."""
        _context: contextlib.AbstractContextManager[str | os.PathLike]
        if not mountpoint:
            _context = tempfile.TemporaryDirectory()
        else:
            _context = contextlib.nullcontext(mountpoint)
        with _context as mountpoint:
            cls.mount(path, mountpoint)
            try:
                yield mountpoint
            finally:
                cls.unmount(mountpoint)


def get_partitions(path: str | os.PathLike) -> tuple[str, ...]:
    """Return tuple of partitions for path to device."""
    return tuple(
        partition
        for partition in glob(f"{path}*", recursive=True)
        if re.search(rf"{path}p?[0-9]+", partition)
    )
