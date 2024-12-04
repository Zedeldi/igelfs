"""Unit tests for the directory."""

from igelfs.constants import DIRECTORY_MAGIC, PartitionType
from igelfs.models import Directory


def test_directory_verify(directory: Directory) -> None:
    """Test verification of directory."""
    assert directory.verify()


def test_directory_magic(directory: Directory) -> None:
    """Test magic string attribute of directory."""
    assert directory.magic == DIRECTORY_MAGIC


def test_directory_free_list(directory: Directory) -> None:
    """Test directory free list."""
    free_list = directory.partition[0]
    assert free_list.type == free_list.get_type() == PartitionType.IGEL_FREELIST


def test_directory_n_fragments(directory: Directory) -> None:
    """Test number of fragments matches directory information."""
    assert directory.n_fragments == directory._get_n_fragments()
