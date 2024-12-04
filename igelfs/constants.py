"""Python implementation of igelsdk.h sourced from igel-flash-driver."""

import math
from enum import IntEnum, IntFlag


class SectionSize(IntEnum):
    """Enumeration for section sizes."""

    SECT_SIZE_64K = 0
    SECT_SIZE_128K = 1
    SECT_SIZE_256K = 2
    SECT_SIZE_512K = 3
    SECT_SIZE_1M = 4
    SECT_SIZE_2M = 5
    SECT_SIZE_4M = 6
    SECT_SIZE_8M = 7
    SECT_SIZE_16M = 8

    @classmethod
    def get(cls: type["SectionSize"], size: int) -> "SectionSize":
        """Get SectionSize for specified size."""
        section_size = int(math.log2(size / 65536))
        return cls(section_size)


class PartitionType(IntEnum):
    """Enumeration for partition types."""

    EMPTY = 0  # partition descriptor is free
    IGEL_RAW = 1  # an uncompressed an writable partition
    IGEL_COMPRESSED = 2  # a compressed read-only partition
    IGEL_FREELIST = 3  # only used by the partition directory
    IGEL_RAW_RO = (
        4  # an uncompressed read-only partition (so CRC is valid and should be checked)
    )
    IGEL_RAW_4K_ALIGNED = (
        5  # an uncompressed an writable partition which is aligned to 4k sectors
    )


class PartitionFlag(IntFlag):
    """Enumeration for partition flags."""

    UPDATE_IN_PROGRESS = 0x100  # flag indicating a not yet to use partition
    HAS_IGEL_HASH = (
        0x200  # flag indicating the presence of a igel hash block after the header
    )
    HAS_CRYPT = 0x400  # flag indicating the presence of a encryption


class ExtentType(IntEnum):
    """Enumeration for extent types."""

    KERNEL = 1
    RAMDISK = 2
    SPLASH = 3
    CHECKSUMS = 4
    SQUASHFS = 5
    WRITEABLE = 6
    LOGIN = 7
    SEC_KERNEL = 8
    DEVICE_TREE = 9
    APPLICATION = 10
    LICENSE = 11


LOG2_SECT_SIZE = SectionSize.SECT_SIZE_256K
IGF_SECTION_SIZE = 0x10000 << (LOG2_SECT_SIZE & 0xF)
IGF_SECTION_SHIFT = 16 + (LOG2_SECT_SIZE & 0xF)

IGF_SECT_HDR_LEN = 32
IGF_SECT_DATA_LEN = IGF_SECTION_SIZE - IGF_SECT_HDR_LEN
IGF_SECT_HDR_MAGIC_UDC = 34086934
IGF_SECT_HDR_MAGIC_OSC = 33628185
IGF_SECT_HDR_MAGIC_OS10 = 34152470
IGF_SECT_HDR_MAGIC_OS11 = 16850969
IGF_SECT_HDR_MAGIC_OS12 = 805642274
IGF_SECT_HDR_MAGIC = [
    IGF_SECT_HDR_MAGIC_UDC,
    IGF_SECT_HDR_MAGIC_OSC,
    IGF_SECT_HDR_MAGIC_OS10,
    IGF_SECT_HDR_MAGIC_OS11,
    IGF_SECT_HDR_MAGIC_OS12,
]
SECTION_IMAGE_CRC_START = 4  # sizeof(uint32_t)
SECTION_END_OF_CHAIN = 0xFFFFFFFF

IGF_MAX_MINORS = 256

EXTENT_MAX_READ_WRITE_SIZE = 0x500000
MAX_EXTENT_NUM = 10

DIRECTORY_MAGIC = "PDIR"  # 0x52494450
CRC_DUMMY = 0x55555555

IGEL_BOOTREG_OFFSET = 0x00000000
IGEL_BOOTREG_SIZE = 0x00008000  # 32K size
IGEL_BOOTREG_MAGIC = 0x4F4F42204C454749  # IGEL BOO

DIR_OFFSET = IGEL_BOOTREG_OFFSET + IGEL_BOOTREG_SIZE  # Starts after the boot registry
DIR_SIZE = (
    IGF_SECTION_SIZE - DIR_OFFSET
)  # Reserve the rest of section #0 for the directory

DIR_MAX_MINORS = 512
MAX_FRAGMENTS = 1404

BOOTSPLASH_MAGIC = "IGELBootSplash"

_HAS_IGEL_BOOTREG_STRUCTURES = 1
BOOTREG_ENC_PLAINTEXT = 0
BOOTREG_MAGIC = "163L"
BOOTREG_IDENT = "IGEL BOOTREGISTRY"
BOOTREG_FLAG_LOCK = 0x0001

_HAS_IGEL_HASH_HEADER = 1
HASH_HDR_IDENT = "chksum"
HASH_SIGNATURE_TYPE_NONE = 0
HASH_ALGO_TYPE_NONE = 0
HASH_BYTE_LEN = 64
SIGNATURE_BYTE_SIZE = 512
