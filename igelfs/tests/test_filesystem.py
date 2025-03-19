"""Unit tests for the filesystem class."""

from igelfs import Filesystem
from igelfs.tests import markers


@markers.slow
def test_filesystem_partition_minors(filesystem: Filesystem) -> None:
    """Test getting partition minors from filesystem."""
    assert filesystem.partition_minors == filesystem.partition_minors_by_directory
