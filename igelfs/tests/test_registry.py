"""Unit tests for registry."""

import os
import sys

import pytest

from igelfs import Filesystem, Registry

pytest.importorskip("lzf")  # required for extent filesystem
kml = pytest.importorskip("igelfs.kml")  # required for decryption


@pytest.mark.skipif(sys.platform != "linux", reason="requires Linux-based platform")
@pytest.mark.skipif(os.getuid() != 0, reason="requires root access for device mapper")
def test_registry_from_filesystem(filesystem: Filesystem) -> None:
    """Test getting registry data from filesystem."""
    registry = Registry.from_filesystem(filesystem)
    for key in registry.keys():
        registry.get(key)
