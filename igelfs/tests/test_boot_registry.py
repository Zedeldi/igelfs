"""Unit tests for the boot registry."""

from igelfs.constants import BOOTREG_IDENT, BOOTREG_MAGIC, IGEL_BOOTREG_SIZE
from igelfs.models import BootRegistryHeader


def test_boot_registry_size(boot_registry: BootRegistryHeader) -> None:
    """Test size of boot registry."""
    size = boot_registry.get_actual_size()
    assert size == boot_registry.get_model_size()
    assert size == IGEL_BOOTREG_SIZE


def test_boot_registry_verify(boot_registry: BootRegistryHeader) -> None:
    """Test verification of boot registry."""
    assert boot_registry.verify()


def test_boot_registry_ident_legacy(boot_registry: BootRegistryHeader) -> None:
    """Test ident_legacy attribute of boot registry."""
    assert boot_registry.ident_legacy == BOOTREG_IDENT


def test_boot_registry_magic(boot_registry: BootRegistryHeader) -> None:
    """Test magic attribute of boot registry."""
    assert boot_registry.magic == BOOTREG_MAGIC
