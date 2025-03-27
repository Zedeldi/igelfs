"""Unit tests for key management."""

import pytest

from igelfs import Filesystem

pytest.importorskip("lzf")  # required for extent filesystem
kml = pytest.importorskip("igelfs.kml")


def test_kml_get_keys(filesystem: Filesystem) -> None:
    """Test extracting encryption keys from filesystem."""
    keyring = kml.Keyring.from_filesystem(filesystem)
    keys = keyring.get_keys()
    assert len(keys) == len(keyring.kml_config["keys"])
