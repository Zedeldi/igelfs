# igelfs

[![GitHub license](https://img.shields.io/github/license/Zedeldi/igelfs?style=flat-square)](https://github.com/Zedeldi/igelfs/blob/master/LICENSE) [![GitHub last commit](https://img.shields.io/github/last-commit/Zedeldi/igelfs?style=flat-square)](https://github.com/Zedeldi/igelfs/commits) [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg?style=flat-square)](https://github.com/psf/black)

Python implementation of the IGEL filesystem.

## Description

`igelfs` provides various data models and methods to interact with an IGEL filesystem image.

`igelfs.models` contains several dataclasses to represent data structures within the filesystem.

Generally, for handling reading from a file, use `igelfs.filesystem.Filesystem`,
which provides methods to obtain sections and access the data structures within them,
in an object-oriented way.

### Models

Models are the foundation for converting raw binary data into OOP data structures.

Most of the higher-level models are taken directly from `igelsdk.h`, with added methods to assist data handling.

`BaseBytesModel` provides an abstract base class, with concrete methods for handling bytes, shared across various models.

`BaseDataModel` is the parent class for all higher-level models.
For these models to be instantiated directly from bytes, they must define `MODEL_ATTRIBUTE_SIZES` as a mapping of dataclass field names to the length of bytes to read.

### Methods

Methods starting with `get` are expected to return a value or raise an exception.
Those starting with `find` will attempt to search for the specified value, returning
`None` if not found.

### LXOS

IGEL firmware update archives can be obtained from their [software downloads](https://www.igel.com/software-downloads/) page.

Files matching the naming convention `lxos_X.Y.Z_public.zip` contain a configuration file named `lxos.inf`.
These files are similar to the INI format, but contain duplicate keys, which would cause [configparser](https://docs.python.org/3/library/configparser.html) to raise an exception (see `strict`), or merge the duplicate sections.
For more information, see this [Wikipedia](https://en.wikipedia.org/wiki/INI_file#Duplicate_names) page.

`igelfs.lxos` contains a `configparser.ConfigParser` subclass, `LXOSParser`, which can be used to parse this configuration file and get values from it.

## Installation

After cloning the repository with: `git clone https://github.com/Zedeldi/igelfs.git`,
install dependencies with `pip install .` or `pip install -r requirements.txt`.

#### Libraries:

-   [RSA](https://pypi.org/project/rsa/) - signature verification

## Credits

-   [IGEL](https://www.igel.com/) - author of `igel-flash-driver`

## License

`igelfs` is licensed under the GPL v3 for everyone to use, modify and share freely.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

[![GPL v3 Logo](https://www.gnu.org/graphics/gplv3-127x51.png)](https://www.gnu.org/licenses/gpl-3.0-standalone.html)

### Original

The original source code, from which this project was derived, can be obtained
by requesting it from IGEL via their [online form](https://www.igel.com/general-public-license/).

`/boot/grub/i386-pc/igelfs.mod` is licensed under the GPL v3.
Requesting a copy of the source code should provide the `igel-flash-driver` kernel module
and initramfs `bootreg` code, written in C.

`/bin/igelfs_util` is copyrighted by IGEL Technology GmbH.

## Donate

If you found this project useful, please consider donating. Any amount is greatly appreciated! Thank you :smiley:

[![PayPal](https://www.paypalobjects.com/webstatic/mktg/Logo/pp-logo-150px.png)](https://paypal.me/ZackDidcott)
