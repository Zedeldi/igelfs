"""Unit tests for the boot registry."""

from igelfs.constants import BOOTREG_IDENT, BOOTREG_MAGIC, IGEL_BOOTREG_SIZE


def test_bootreg_size(bootreg) -> None:
    """Test size of boot registry."""
    assert bootreg.size == IGEL_BOOTREG_SIZE


def test_bootreg_verify(bootreg) -> None:
    """Test verification of boot registry."""
    assert bootreg.verify()


def test_bootreg_ident_legacy(bootreg) -> None:
    """Test ident_legacy attribute of boot registry."""
    assert bootreg.ident_legacy == BOOTREG_IDENT


def test_bootreg_magic(bootreg) -> None:
    """Test magic attribute of boot registry."""
    assert bootreg.magic == BOOTREG_MAGIC
