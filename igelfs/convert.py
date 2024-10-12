"""Module to assist converting IGEL Filesystem to other formats."""

import re
from contextlib import contextmanager
from glob import glob
from pathlib import Path
from typing import Iterator

import parted

from igelfs.filesystem import Filesystem
from igelfs.lxos import LXOSParser
from igelfs.models import Section
from igelfs.utils import run_process


class Disk:
    """Class to handle Filesystem as a standard disk with a partition table."""

    def __init__(self, path: str | Path) -> None:
        """Initialize disk instance."""
        self.path = Path(path).resolve()

    def allocate(self, size: int, zero: bool = False) -> None:
        """Create empty file of specified size."""
        with open(self.path, "wb") as fd:
            if zero:
                fd.write(bytes(size))
            else:
                fd.truncate(size)

    def partition(
        self, filesystem: Filesystem, lxos_config: LXOSParser | None = None
    ) -> None:
        """
        Create a partition table on the block device.

        The disk will have the following:
          - GPT partition table
          - Partitions for each partition in IGEL filesystem
              - Partition names matching partition_minor if lxos_config specified
        """
        device = parted.getDevice(self.path.as_posix())
        disk = parted.freshDisk(device, "gpt")
        for partition_minor in filesystem.partition_minors_by_directory:
            sections = filesystem.find_sections_by_directory(partition_minor)
            payload = Section.get_payload_of(sections)
            # Get start of free region at end of disk
            start = disk.getFreeSpaceRegions()[-1].start
            length = parted.sizeToSectors(len(payload), "B", device.sectorSize)
            geometry = parted.Geometry(device=device, start=start, length=length)
            partition = parted.Partition(
                disk=disk, type=parted.PARTITION_NORMAL, geometry=geometry
            )
            disk.addPartition(
                partition=partition, constraint=device.optimalAlignedConstraint
            )
            if lxos_config:
                name = lxos_config.find_name_by_partition_minor(partition_minor)
                if name:
                    partition.set_name(name)
        disk.commit()

    def write(self, filesystem: Filesystem) -> None:
        """Write filesystem data to partitions."""
        with loop_device(self.path) as device:
            for partition, partition_minor in zip(
                get_partitions(device), filesystem.partition_minors_by_directory
            ):
                sections = filesystem.find_sections_by_directory(partition_minor)
                payload = Section.get_payload_of(sections)
                with open(partition, "wb") as fd:
                    fd.write(payload)

    @classmethod
    def from_filesystem(
        cls: type["Disk"],
        path: str | Path,
        filesystem: Filesystem,
        lxos_config: LXOSParser | None = None,
    ) -> "Disk":
        """Convert filesystem to disk image and return Disk."""
        disk = cls(path)
        if not disk.path.exists():
            disk.allocate(filesystem.size)
        disk.partition(filesystem, lxos_config)
        disk.write(filesystem)
        return disk


@contextmanager
def loop_device(path: str | Path) -> Iterator[str]:
    """Context manager to attach path as loop device, then detach on closing."""
    loop_device = losetup_attach(path)
    try:
        yield loop_device
    finally:
        losetup_detach(loop_device)


def losetup_attach(path: str | Path) -> str:
    """Attach specified path as loop device, returning device path."""
    return run_process(["losetup", "--partscan", "--find", "--show", path])


def losetup_detach(path: str | Path) -> None:
    """Detach specified loop device."""
    run_process(["losetup", "--detach", path])


def get_partitions(path: str | Path) -> tuple[str]:
    """Return tuple of partitions for path to device."""
    return tuple(
        partition
        for partition in glob(f"{path}*", recursive=True)
        if re.search(rf"{path}p?[0-9]+", partition)
    )
