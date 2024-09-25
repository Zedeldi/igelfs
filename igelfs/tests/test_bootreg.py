"""Unit tests for the boot registry."""

from igelfs.constants import BOOTREG_IDENT, BOOTREG_MAGIC, IGEL_BOOTREG_SIZE
from igelfs.models import BootRegistryHeader


def test_bootreg_size(bootreg: BootRegistryHeader) -> None:
    """Test size of boot registry."""
    size = bootreg.get_actual_size()
    assert size == bootreg.get_model_size()
    assert size == IGEL_BOOTREG_SIZE


def test_bootreg_verify(bootreg: BootRegistryHeader) -> None:
    """Test verification of boot registry."""
    assert bootreg.verify()


def test_bootreg_ident_legacy(bootreg: BootRegistryHeader) -> None:
    """Test ident_legacy attribute of boot registry."""
    assert bootreg.ident_legacy == BOOTREG_IDENT


def test_bootreg_magic(bootreg: BootRegistryHeader) -> None:
    """Test magic attribute of boot registry."""
    assert bootreg.magic == BOOTREG_MAGIC
