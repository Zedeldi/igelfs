# igelfs

[![GitHub license](https://img.shields.io/github/license/Zedeldi/igelfs?style=flat-square)](https://github.com/Zedeldi/igelfs/blob/master/LICENSE) [![GitHub last commit](https://img.shields.io/github/last-commit/Zedeldi/igelfs?style=flat-square)](https://github.com/Zedeldi/igelfs/commits) [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg?style=flat-square)](https://github.com/psf/black)

Python implementation of the IGEL filesystem.

## Description

`igelfs` provides various data models and methods to interact with an IGEL filesystem image.

`igelfs.models` contains several dataclasses to represent data structures within the filesystem.

Generally, for handling reading from a file/device, use `igelfs.filesystem.Filesystem`,
which provides methods to obtain sections and access the data structures within them,
in an object-oriented way.
`Filesystem` also provides simple methods to write bytes/sections.

### Filesystem

Once installed, there are usually three partitions on UEFI systems, in the following format:

-   Partition #1
    -   IGEL FS
-   Partition #2
    -   FAT32, ESP #1
-   Partition #3
    -   FAT32, ESP #2

For OS 12, it appears the IGEL FS partition is #4, and partition #1 is small (~9 MiB) and filled with null bytes.

Please see the following snippet from `igelfs.__init__` for a description of the filesystem structure:

>   -   Section #0
>       -   Boot Registry
>           -   Boot Registry Entries
>       - Directory
>           -   Partition Descriptors
>           -   Fragment Descriptors
>   -   Section #1, Partition Minor #1
>       -   Section Header
>       -   Partition Block
>           -   Partition Header
>           -   Partition Extents * `PartitionHeader.n_extents`
>       -   Hash Block, optional
>           -   Hash Header
>           -   Hash Excludes * `HashHeader.count_excludes`
>           -   Hash Values => `HashHeader.hash_block_size`
>       -   Partition Data
>           - Extents
>           - Payload
>   -   Section #2, Partition Minor #1
>       -   Section Header
>       -   Partition Data
>   -   Section #3, Partition Minor #2...
>
>   In short, all partitions are stored in sections as a linked list.
>   Each section has a section header, which contains the partition minor (ID)
>   and the next section for the partition until `0xffffffff`.
>   The first section of a partition also contains a partition header
>   and optionally a hash header.

For more information about these data structures, see [models](#models).

### Models

Models are the foundation for converting raw binary data into OOP data structures.

Most of the higher-level models are taken directly from `igelsdk.h`, with added methods to assist data handling.

`BaseBytesModel` provides an abstract base class, with concrete methods for handling bytes, shared across various models.

`BaseDataModel` is the parent class for all higher-level models.
For these models to be instantiated directly from bytes, they must define fields
with metadata containing the size of bytes to read.
To set default values when instantiating models from nothing with `new`,
add the `default` value to the metadata of the field.

#### Section

-   Stores section header, partition block, hash block and payload
-   Contains a `__post_init__` magic dataclass method to parse payload into additional data groups
-   Has methods to calculate hash, split into or extract data, such as partition extents, from sections

#### Partition

-   Stores partition header and extent information; the actual extent payload is stored at the beginning of the section payload, and can span multiple sections
-   Provides methods to parse partition and extent information

#### Hash

-   Data group to store hash header, excludes and values
-   Implements calculating hashes, getting digest values and verifying signatures

#### Boot Registry

-   Stores basic boot information and boot registry entries
-   Legacy format uses `\n`-separated `key=value` pairs, terminated by `EOF`
-   New format uses fixed-size entry models with a 2-byte flag to indicate size and continuation

#### Directory

-   Stores directory information to look-up locations of partitions efficiently, without linearly searching the entire filesystem
-   Find:
    -   Partition descriptor by partition minor
    -   Fragment descriptor by partition descriptor attribute (`first_fragment`)
    -   First section of partition by fragment descriptor attribute (`first_section`)

#### Bootsplash

-   Stores extent information from bootsplash partition
-   Contains bootsplash header, list of bootsplash information models and payload
-   Provides method to obtain [`PIL.Image.Image`](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image) instances from payload

### Methods

Methods starting with `get` are expected to return a value or raise an exception.
Those starting with `find` will attempt to search for the specified value, returning
`None` if not found.

### LXOS/OSIV

IGEL firmware update archives can be obtained from their [software downloads](https://www.igel.com/software-downloads/) page.

Files matching the naming convention `lxos_X.Y.Z_public.zip` contain a configuration file named `lxos.inf`.
In the case of OS 10/UDC, this configuration file is called `osiv.inf`.

These files are similar to the INI format, but contain duplicate keys, which would cause [configparser](https://docs.python.org/3/library/configparser.html) to raise an exception (see `strict`), or merge the duplicate sections.
For more information, see this [Wikipedia](https://en.wikipedia.org/wiki/INI_file#Duplicate_names) page.

`igelfs.lxos` contains a `configparser.ConfigParser` subclass, `LXOSParser`, which can be used to parse this configuration file and get values from it.

### Verification

The integrity of a section is confirmed by the CRC32 checksum in the section header and the hash block (if present).

When setting these values, it must be calculated in the following order: hash, signature (depends on hash), CRC32 (influenced by previous values).

#### Checksum

The CRC32 checksum is calculated from all of the bytes in a section, starting at `CRC_OFFSET`, which excludes the checksum value itself from the input.

#### Hash

The hash values are calculated using the [BLAKE2b](https://en.wikipedia.org/wiki/BLAKE_(hash_function)) algorithm with a digest size specified in `hash_bytes`, from all sections in a partition, excluding the indicies specified by the ranges in the hash excludes.
The start, end and size are based on absolute addresses not relative to section or partition headers.
Excluded bytes are replaced with null bytes (`\x00`).

Please see the docstring below from `igelfs.models.hash.HashExclude` for more information:

>   The following bytes are normally excluded for each section (inclusive):
>   -   0-3 => `SectionHeader.crc`
>   -   16-17 => `SectionHeader.generation`
>   -   22-25 => `SectionHeader.next_section`
>
>   The following bytes are normally excluded for section zero (inclusive, shifted by partition extents):
>   -   164-675 => `HashHeader.signature`
>   -   836-836 + (`HashHeader.hash_bytes` * `HashHeader.count_hash`) => `Section.hash_value`

Similarly to the `CRC_OFFSET`, the hash excludes serve to remove dynamic values from the hash input;
only the payload and metadata of the section is verified.

#### Signature

The hash block also contains a signature of all hash values and excludes, using [SHA-256](https://en.wikipedia.org/wiki/SHA-2).
The public keys to verify these signatures can be found in `igelfs.keys`.

This confirms the authenticity of the data, and prevents modifying the hash values.

### Boot Process

The boot process of IGEL OS is important when considering the structure of the file system.

#### Kernel

For example, once installed, the Linux kernel is stored as a partition extent of the `sys` (partition minor 1) partition.

When querying the file type, you should receive output similar to the following:

`Linux kernel x86 boot executable bzImage, version 4.19.65 (IGEL@ITGA) #mainline-udos`

Where the kernel version and OS edition, e.g. `udos`, `lxos` or `lxos12`, will vary.

For IGEL OS installation media, the kernel is stored as a separate bzImage file on disk - not as a partition extent.
Additionally, the IGEL filesystem image is stored alongside the kernel, named `ddimage.bin`.

#### UEFI

For UEFI systems, the boot process is described below:

1.  `bootx64.efi` or `bootia32.efi` (signed by `/C=US/ST=Washington/L=Redmond/O=Microsoft Corporation/CN=Microsoft Corporation UEFI CA 2011`)
    1.  These images are signed (by Microsoft) shims to hand off execution to GRUB
    2.  The source code for these images can be found at the following forks:
        [igelboot](https://github.com/igelboot/shim/tree/igel-shim)
        and [IGEL-Technology](https://github.com/IGEL-Technology/shim)
    3.  These were reviewed by the [SHIM review board](https://github.com/rhboot/shim-review)
        via [issue #11](https://github.com/rhboot/shim-review/issues/11) ([review](https://github.com/igelboot/shim-review))
        and [issue #434](https://github.com/rhboot/shim-review/issues/434) ([review](https://github.com/IGEL-Technology/shim-review))
        respectively
    4.  These were then submitted and signed by Microsoft according to
        these [instructions](https://techcommunity.microsoft.com/blog/hardwaredevcenter/updated-uefi-signing-requirements/1062916)
2.  `igelx64.efi` or `igelia32.efi` (signed by `/CN=IGEL Secure Boot Signing CA/O=IGEL Technology GmbH/L=Bremen/C=DE`)
    1.  These images are signed (by IGEL) GRUB binaries
    2.  The kernel is also signed by this key
    3.  These certificates can be downloaded from the following links:
        [igel-efi-pub-key (2017-2047)](https://github.com/igelboot/shim/blob/igel-shim/igel-efi-pub-key.der)
        and [igel-uefi-ca (2024-2054)](https://github.com/IGEL-Technology/shim-review/blob/main/igel-uefi-ca.der)
3.  GRUB loads signed `igelfs.mod` to load and boot kernel from IGEL filesystem
    1.  The initramfs is embedded into the kernel (`bzImage`)
    2.  For IGEL OS installation media, the kernel is stored as a separate file on disk,
        not within an IGEL filesystem (see [above](#kernel))
4.  The system partition (squashfs, usually zstd compressed) is mounted from initramfs
    1. The root directory is changed to `/igfimage`
    2. Real `init` (`systemd`) process is started

This extract from a [Red Hat article](https://access.redhat.com/articles/5991201) describes the initial boot process clearly:

>   shim is a first-stage boot loader that embeds a self-signed Certificate Authority (CA) certificate.
>   Microsoft signs shim binaries, which ensures that they can be booted on all machines with a pre-loaded Microsoft certificate.
>   shim uses the embedded certificate to verify the signature of the GRUB 2 boot loader.
>   shim also provides a protocol that GRUB 2 uses to verify the kernel signature.

## Installation

1.  Clone the repository: `git clone https://github.com/Zedeldi/igelfs.git`
2.  Install project: `pip install .`
3.  **or** install dependencies: `pip install -r requirements.txt`

### Libraries

-   [rsa](https://pypi.org/project/rsa/) - signature verification
-   [pillow](https://pypi.org/project/pillow/) - bootsplash images
-   [python-magic](https://pypi.org/project/python-magic/) - payload identification
-   [pyparted](https://pypi.org/project/pyparted/) - disk conversion (optional)
-   [pytest](https://pypi.org/project/pytest/) - testing, see [below](#testing)

## Usage

If the project is installed: `igelfs-cli --help`

Otherwise, you can run the module as a script: `python -m igelfs.cli --help`

By default, filesystem partition information will be displayed.

## Testing

Tests rely on the `pytest` testing framework.

To test the project (or the sanity of a filesystem image), use:
`python -m pytest --image="path/to/filesystem" --inf="path/to/lxos.inf" igelfs`

Specify `-m "not slow"` to skip slow tests.

## Credits

-   [IGEL](https://www.igel.com/) - author of `igel-flash-driver`

## License

`igelfs` is licensed under the GPL v3 for everyone to use, modify and share freely.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

[![GPL v3 Logo](https://www.gnu.org/graphics/gplv3-127x51.png)](https://www.gnu.org/licenses/gpl-3.0-standalone.html)

### Original

The original source code, from which this project was derived, can be obtained
by requesting it from IGEL via their [online form](https://www.igel.com/general-public-license/)
or via this [GitHub repository](https://github.com/IGEL-Technology/igel-flash-driver).

`/boot/grub/i386-pc/igelfs.mod` is licensed under the GPL v3.
Requesting a copy of the source code should provide the `igel-flash-driver` kernel module
and initramfs `bootreg` code, written in C.

`/bin/igelfs_util` is copyrighted by IGEL Technology GmbH.

## Donate

If you found this project useful, please consider donating. Any amount is greatly appreciated! Thank you :smiley:

[![PayPal](https://www.paypalobjects.com/webstatic/mktg/Logo/pp-logo-150px.png)](https://paypal.me/ZackDidcott)
