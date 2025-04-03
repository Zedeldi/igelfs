"""
Python interface for the IGEL filesystem.

For a standard IGEL OS disk image, the layout is similar to the below:
- Partition 1
  - IGEL FS
- Partition 2
  - FAT32, ESP #1
- Partition 3
  - FAT32, ESP #2

IGEL FS has the following layout:
- Section #0
  - Boot Registry
    - Boot Registry Entries
  - Directory
    - Partition Descriptors
    - Fragment Descriptors
- Section #1, Partition Minor #1
  - Section Header
  - Partition Block
    - Partition Header
    - Partition Extents * PartitionHeader.n_extents
  - Hash Block, optional
    - Hash Header
    - Hash Excludes * HashHeader.count_excludes
    - Hash Values => HashHeader.hash_block_size
  - Partition Data
    - Extents
    - Payload
- Section #2, Partition Minor #1
  - Section Header
  - Partition Data
- Section #3, Partition Minor #2...

In short, all partitions are stored in sections as a linked list.
Each section has a section header, which contains the partition minor (ID)
and the next section for the partition until 0xffffffff.
The first section of a partition also contains a partition header
and optionally a hash header.

The directory contains a list of partition and fragment descriptors, which
can be used to find the first section index for a given partition minor, without
the need for linearly searching the entire image.
"""

from igelfs import constants, models
from igelfs.filesystem import Filesystem
from igelfs.keys import IGEL_PUBLIC_KEYS
from igelfs.lxos import LXOSParser
from igelfs.registry import Registry

__all__ = [
    "Filesystem",
    "IGEL_PUBLIC_KEYS",
    "LXOSParser",
    "Registry",
    "constants",
    "models",
]
