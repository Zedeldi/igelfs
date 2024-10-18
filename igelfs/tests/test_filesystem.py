"""Unit tests for the filesystem class."""

import pytest

from igelfs import Filesystem


@pytest.mark.slow
def test_filesystem_partition_minors(filesystem: Filesystem) -> None:
    """Test getting partition minors from filesystem."""
    assert filesystem.partition_minors == filesystem.partition_minors_by_directory
