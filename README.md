# igelfs

[![GitHub license](https://img.shields.io/github/license/Zedeldi/igelfs?style=flat-square)](https://github.com/Zedeldi/igelfs/blob/master/LICENSE) [![GitHub last commit](https://img.shields.io/github/last-commit/Zedeldi/igelfs?style=flat-square)](https://github.com/Zedeldi/igelfs/commits) [![PyPI version](https://img.shields.io/pypi/v/igelfs?style=flat-square)](https://pypi.org/project/igelfs/) [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg?style=flat-square)](https://github.com/psf/black)

Python implementation of the IGEL filesystem.

## Description

`igelfs` provides various data models and methods to interact with an IGEL filesystem image.

`igelfs.models` contains several dataclasses to represent data structures within the filesystem.

Generally, for handling reading from a file/device, use `igelfs.Filesystem`,
which provides methods to obtain sections and access the data structures within them,
in an object-oriented way.
`Filesystem` also provides simple methods to write bytes/sections.

A command-line interface is also provided for common filesystem operations.

## Documentation

For documentation and other information, please see the [wiki](https://github.com/Zedeldi/igelfs/wiki).

## Installation

### PyPI

1.  Install project: `pip install igelfs`

The project page can be found [here](https://pypi.org/project/igelfs/).

### Source

1.  Clone the repository: `git clone https://github.com/Zedeldi/igelfs.git`
2.  Install project: `pip install .`
3.  **or** install dependencies: `pip install -r requirements.txt`

### Libraries

- [rsa](https://pypi.org/project/rsa/) - signature verification
- [pillow](https://pypi.org/project/pillow/) - bootsplash images
- [python-magic](https://pypi.org/project/python-magic/) - payload identification
- [pyparted](https://pypi.org/project/pyparted/) - disk conversion (optional)
- [cryptography](https://pypi.org/project/cryptography/) - encryption (optional)
- [PyNaCl](https://pypi.org/project/PyNaCl/) - encryption, bindings to [libsodium](https://github.com/jedisct1/libsodium) (optional)
- [python-lzf](https://pypi.org/project/python-lzf/) - compression, bindings to liblzf (optional)
- [pytest](https://pypi.org/project/pytest/) - testing, see [below](#testing)

## Usage

If the project is installed: `igelfs-cli --help`

Otherwise, you can run the module as a script: `python -m igelfs.cli --help`

For more information, head over to the [wiki](https://github.com/Zedeldi/igelfs/wiki/Usage).

## Testing

Tests rely on the `pytest` testing framework.

To test the project (or the sanity of a filesystem image), use:
`python -m pytest --image="path/to/filesystem" --inf="path/to/lxos.inf" igelfs`

Specify `-m "not slow"` to skip slow tests.

## Credits

- [IGEL](https://www.igel.com/) - author of `igel-flash-driver`

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
