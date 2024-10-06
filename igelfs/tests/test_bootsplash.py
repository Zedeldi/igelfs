"""Unit tests for the bootsplash models."""

import pytest

from igelfs.constants import BOOTSPLASH_MAGIC
from igelfs.filesystem import Filesystem
from igelfs.lxos import LXOSParser
from igelfs.models import BootsplashHeader


@pytest.mark.inf
def test_bootsplash_magic(filesystem: Filesystem, parser: LXOSParser) -> None:
    """Test magic string attribute of bootsplash header."""
    for key in parser:
        if not key.startswith("PART"):
            continue
        if parser.get(key, "name") == "bspl":
            partition_minor = parser.getint(key, "number")
            break
    else:
        pytest.skip(reason="Bootsplash partition not found")
    bootsplash = filesystem.find_sections_by_directory(partition_minor)
    bootsplash_header = BootsplashHeader.from_bytes(bootsplash[0].data)
    assert bootsplash_header.magic == BOOTSPLASH_MAGIC
