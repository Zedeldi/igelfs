"""
Module to handle factory reset of IGEL OS.

To reset to factory defaults, press ESC at GRUB to display the menu.
Then, select "Reset to factory defaults". If an administrator password is
set, and it is not known, a reset key will need to be entered.
The on-screen instructions advise the user to contact IGEL support to
obtain this key.

This sets the systemd.unit=igel-reset-to-factory-defaults.target on the
kernel command-line, which changes to TTY11 and wants
igel-reset-terminal@tty11, starting /sbin/reset_terminal.

The terminal key is read from /wfs/systemrandom.
If the reset key is entered correctly, /bin/reset_to_defaults is executed, which
executes /etc/reset_terminal_to_factory_defaults, removing any custom partitions
and most boot registry entries.

To generate the "reset to defaults key", the "terminal key" is encrypted with
the Triple DES (3DES) cipher (https://en.wikipedia.org/wiki/Triple_DES).

However, as the IV changes on each iteration, this has been implemented with
separate DES ciphers.

The terminal key is formatted as four denary numbers, separated by dashes, where
each value is less than or equal to 65535 (0xFFFF):
00000-00000-00000-00000

Based on https://github.com/thomasDOTwtf/free_stacheltier.
"""

import sys

from igelfs.filesystem import Filesystem
from igelfs.wfs import WfsPartition

try:
    from igelfs.crypto import CryptoHelper
except ImportError:
    _CRYPTO_AVAILABLE = False
else:
    _CRYPTO_AVAILABLE = True


class FactoryReset:
    """Class to handle factory reset keys."""

    KEYS = [
        b"\x72\x02\x53\xb6\x77\x79\xad\x96",
        b"\x56\x59\x12\x95\x89\xaa\x76\x33",
        b"\x34\x49\xd6\xa9\xc7\x55\x67\x28",
    ]
    IVS = [
        b"\x3b\x52\x7f\x6e\x97\xf8\xaa\x16",
        b"\xc1\x92\x88\x48\x49\x05\x11\x19",
        b"\xf4\x41\x71\x68\x37\x73\xb1\x02",
    ]
    KEY_SEPARATOR = "-"
    SYSTEM_RANDOM_FILENAME = "systemrandom"

    def __init__(self, terminal_key: str) -> None:
        """Initialise and validate instance."""
        if not self.validate_key(terminal_key):
            raise ValueError(f"Invalid terminal key: {terminal_key}")
        self.terminal_key = terminal_key

    def get_reset_key(self) -> str:
        """Return 'reset to defaults key' from 'terminal key' challenge."""
        if not _CRYPTO_AVAILABLE:
            raise ImportError("Cryptographic functionality is not available")
        terminal_key = self.key_to_bytes(self.terminal_key)
        reset_key = CryptoHelper.triple_des_cbc_encrypt(
            terminal_key, keys=self.KEYS, ivs=self.IVS
        )
        return self.bytes_to_key(reset_key)

    @classmethod
    def validate_key(cls: type["FactoryReset"], key: str) -> bool:
        """Return whether key is valid."""
        parts = key.split(cls.KEY_SEPARATOR)
        return len(parts) == 4 and all(int(part) <= 0xFFFF for part in parts)

    @classmethod
    def key_to_bytes(cls: type["FactoryReset"], key: str) -> bytes:
        """Return bytes from key string."""
        return b"".join(
            int(part).to_bytes(2, byteorder="little")
            for part in key.split(cls.KEY_SEPARATOR, maxsplit=3)
        )

    @classmethod
    def bytes_to_key(cls: type["FactoryReset"], key: bytes) -> str:
        """Return key string from bytes."""
        return cls.KEY_SEPARATOR.join(
            map(
                str,
                (
                    int.from_bytes(key[index : index + 2], byteorder="little")
                    for index in range(0, len(key), 2)
                ),
            )
        )

    @classmethod
    def from_filesystem(
        cls: type["FactoryReset"], filesystem: Filesystem
    ) -> "FactoryReset":
        """Return FactoryReset instance from filesystem."""
        with WfsPartition(filesystem) as mountpoint:
            try:
                with open(mountpoint / cls.SYSTEM_RANDOM_FILENAME, "r") as file:
                    terminal_key = file.read()
            except FileNotFoundError:
                raise ValueError("File for terminal key does not exist") from None
        return cls(terminal_key=terminal_key)


def main() -> None:
    """Generate and print reset key from passed terminal key."""
    terminal_key = sys.argv[1]
    reset_key = FactoryReset(terminal_key).get_reset_key()
    print(reset_key)


if __name__ == "__main__":
    main()
