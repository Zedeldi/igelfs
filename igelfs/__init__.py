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
- Section #1...
  - Section Header
  - Partition
    - Partition Header
    - Partition Payload
"""

from igelfs.filesystem import Filesystem, Section
from igelfs.models import BootRegistryHeader, Directory, PartitionHeader, SectionHeader

__all__ = [
    "BootRegistryHeader",
    "Directory",
    "Filesystem",
    "PartitionHeader",
    "Section",
    "SectionHeader",
]
