"""Data models for various IGEL filesystem structures."""

from igelfs.models.boot_registry import (
    BootRegistryEntry,
    BootRegistryHeader,
    BootRegistryHeaderFactory,
    BootRegistryHeaderLegacy,
)
from igelfs.models.bootsplash import Bootsplash, BootsplashExtent, BootsplashHeader
from igelfs.models.collections import DataModelCollection
from igelfs.models.directory import Directory, FragmentDescriptor, PartitionDescriptor
from igelfs.models.efs import ExtentFilesystem
from igelfs.models.hash import Hash, HashExclude, HashHeader, HashInformation
from igelfs.models.partition import (
    Partition,
    PartitionExtent,
    PartitionExtentReadWrite,
    PartitionExtents,
    PartitionHeader,
)
from igelfs.models.section import Section, SectionHeader

__all__ = [
    "BootRegistryEntry",
    "BootRegistryHeader",
    "BootRegistryHeaderFactory",
    "BootRegistryHeaderLegacy",
    "Bootsplash",
    "BootsplashExtent",
    "BootsplashHeader",
    "DataModelCollection",
    "Directory",
    "ExtentFilesystem",
    "FragmentDescriptor",
    "Hash",
    "HashExclude",
    "HashHeader",
    "HashInformation",
    "Partition",
    "PartitionDescriptor",
    "PartitionExtent",
    "PartitionExtentReadWrite",
    "PartitionExtents",
    "PartitionHeader",
    "Section",
    "SectionHeader",
]
