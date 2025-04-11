"""Module to assist converting IGEL Filesystem to other formats."""

import logging
import os
from pathlib import Path

import parted

from igelfs.device import Losetup, get_partitions
from igelfs.filesystem import Filesystem
from igelfs.lxos import LXOSParser
from igelfs.models import Section

logger = logging.getLogger(__name__)


class Disk:
    """Class to handle Filesystem as a standard disk with a partition table."""

    def __init__(self, path: str | os.PathLike) -> None:
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

        Partitions are ordered by partition minor.
        """
        logger.info(f"Initialising GPT partition table in '{self.path}'")
        device = parted.getDevice(self.path.as_posix())
        disk = parted.freshDisk(device, "gpt")
        for partition_minor in sorted(filesystem.partition_minors_by_directory):
            sections = filesystem.find_sections_by_directory(partition_minor)
            payload = Section.get_payload_of(sections)
            # Get start of free region at end of disk
            start = disk.getFreeSpaceRegions()[-1].start
            length = parted.sizeToSectors(len(payload), "B", device.sectorSize)
            geometry = parted.Geometry(device=device, start=start, length=length)
            partition = parted.Partition(
                disk=disk, type=parted.PARTITION_NORMAL, geometry=geometry
            )
            logger.debug(f"Adding partition at {start} of length {length} sectors")
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
        with Losetup(self.path) as device:
            for partition, partition_minor in zip(
                sorted(get_partitions(device), key=lambda partition: partition.index),
                sorted(filesystem.partition_minors_by_directory),
            ):
                sections = filesystem.find_sections_by_directory(partition_minor)
                payload = Section.get_payload_of(sections)
                logger.info(f"Writing partition {partition_minor} to {partition.path}")
                with open(partition.path, "wb") as fd:
                    fd.write(payload)

    @classmethod
    def from_filesystem(
        cls: type["Disk"],
        path: str | os.PathLike,
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
