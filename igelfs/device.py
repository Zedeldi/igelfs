"""
Functions to handle device operations.

These helper classes rely on various binaries available on Linux-based
platforms, e.g. cryptsetup, losetup, mount.
Device operations are not available on other platforms.

Classes inheriting from BaseContext can be used as a context manager, closing
or removing the mapped/mounted device on exiting the context. Alternatively,
they can be used as standalone helper classes with static methods.
"""

import contextlib
import logging
import os
import re
import subprocess
import tempfile
import uuid
from collections.abc import Generator
from dataclasses import dataclass
from glob import glob
from pathlib import Path

from igelfs.utils import BaseContext, run_process

logger = logging.getLogger(__name__)


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
        logger.debug(
            f"Opening LUKS container at '{path}' with name '{name}' and keyfile '{keyfile}'"
        )
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
        logger.debug(
            f"Opening encrypted container at '{path}' with name '{name}' and keyfile '{keyfile}'"
        )
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
        logger.debug(f"Attaching '{path}' as loop device")
        return run_process(["losetup", "--partscan", "--find", "--show", path])

    @staticmethod
    def detach(path: str | os.PathLike) -> None:
        """Detach specified loop device."""
        logger.debug(f"Detaching loop device '{path}'")
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
        logger.debug(f"Mounting '{path}' to '{mountpoint}'")
        run_process(["mount", path, mountpoint])

    @staticmethod
    def unmount(mountpoint: str | os.PathLike) -> None:
        """Unmount device mounted at mountpoint."""
        logger.debug(f"Unmounting '{mountpoint}'")
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


@dataclass
class PartitionDescriptor:
    """Dataclass to describe a partition path."""

    path: str
    index: int
    device: str | os.PathLike


def get_parent_device(
    path: str | os.PathLike, prefix: str | os.PathLike = "/dev"
) -> Path:
    """Return path to parent device from path."""
    path = Path(path)
    if not path.is_block_device():
        raise ValueError(f"Path '{path}' is not a block device")
    device = Path("/sys/class/block/") / path.name
    return Path(prefix) / device.resolve().parent.name


def get_partition_index(path: str | os.PathLike, partition: str) -> int | None:
    """Return partition index from path."""
    return (
        int(match.group(1))
        if (match := re.search(rf"{path}p?([0-9]+)", partition))
        else match
    )


def get_partitions(path: str | os.PathLike) -> tuple[PartitionDescriptor, ...]:
    """Return tuple of partition descriptors for path to device."""
    return tuple(
        PartitionDescriptor(partition, index, device=path)
        for partition in glob(f"{path}*", recursive=True)
        if (index := get_partition_index(path, partition))  # Filter out None
    )
