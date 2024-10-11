"""Module to assist converting IGEL Filesystem to other formats."""

from pathlib import Path

import parted

from igelfs.filesystem import Filesystem
from igelfs.lxos import LXOSParser
from igelfs.models import Section


class Disk:
    """Class to handle Filesystem as a standard disk with a partition table."""

    def __init__(self, path: str | Path) -> None:
        """Initialize disk instance."""
        self.path = path

    def allocate(self, size: int) -> None:
        """Create empty file of specified size."""
        with open(self.path, "wb") as fd:
            fd.write(bytes(size))

    def partition(
        self, filesystem: Filesystem, lxos_config: LXOSParser | None = None
    ) -> None:
        """
        Create a partition table on the block device.

        The disk will have the following:
          - GPT partition table
          - Partitions for each partition in IGEL Filesystem
              - Partition names matching partition_minor if lxos_config specified
        """
        device = parted.getDevice(self.path)
        disk = parted.freshDisk(device, "gpt")
        for partition_minor in filesystem.partition_minors_by_directory:
            sections = filesystem.find_sections_by_directory(partition_minor)
            payload = Section.get_payload_of(sections)
            start = disk.getFreeSpaceRegions()[0].start
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
