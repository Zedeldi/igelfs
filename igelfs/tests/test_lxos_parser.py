"""Unit tests for the LXOS configuration parser."""

import pytest

from igelfs.lxos import LXOSParser
from igelfs.tests import markers


@markers.inf
@pytest.mark.parametrize("name,expected", [("sys", 1), ("bspl", 23)])
def test_parser_find_partition_minor(
    parser: LXOSParser, name: str, expected: int
) -> None:
    """Test finding partition minor from name."""
    partition_minor = parser.find_partition_minor_by_name(name)
    assert partition_minor == expected


@markers.inf
@pytest.mark.parametrize("partition_minor,expected", [(1, "sys"), (23, "bspl")])
def test_parser_find_partition_name(
    parser: LXOSParser, partition_minor: int, expected: str
) -> None:
    """Test finding name from partition minor."""
    name = parser.find_name_by_partition_minor(partition_minor)
    assert name == expected
