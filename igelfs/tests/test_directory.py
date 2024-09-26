"""Unit tests for the directory."""

from igelfs.constants import DIRECTORY_MAGIC
from igelfs.models import Directory


def test_directory_verify(directory: Directory) -> None:
    """Test verification of directory."""
    assert directory.verify()


def test_directory_magic(directory: Directory) -> None:
    """Test magic string attribute of directory."""
    assert directory.magic == DIRECTORY_MAGIC
