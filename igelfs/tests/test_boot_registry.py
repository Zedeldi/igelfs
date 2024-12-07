"""Unit tests for the boot registry."""

import pytest

from igelfs.constants import BOOTREG_IDENT, BOOTREG_MAGIC, IGEL_BOOTREG_SIZE
from igelfs.models import BootRegistryHeader, BootRegistryHeaderLegacy


def test_boot_registry_size(
    boot_registry: BootRegistryHeader | BootRegistryHeaderLegacy,
) -> None:
    """Test size of boot registry."""
    size = boot_registry.get_actual_size()
    assert size == boot_registry.get_model_size()
    assert size == IGEL_BOOTREG_SIZE


def test_boot_registry_verify(
    boot_registry: BootRegistryHeader | BootRegistryHeaderLegacy,
) -> None:
    """Test verification of boot registry."""
    assert boot_registry.verify()


def test_boot_registry_ident_legacy(
    boot_registry: BootRegistryHeader | BootRegistryHeaderLegacy,
) -> None:
    """Test ident_legacy attribute of boot registry."""
    assert boot_registry.ident_legacy == BOOTREG_IDENT


def test_boot_registry_magic(
    boot_registry: BootRegistryHeader | BootRegistryHeaderLegacy,
) -> None:
    """Test magic attribute of boot registry."""
    if isinstance(boot_registry, BootRegistryHeaderLegacy):
        pytest.skip("Legacy boot registry header does not have a magic attribute")
    assert boot_registry.magic == BOOTREG_MAGIC


def test_boot_registry_get_entries(
    boot_registry: BootRegistryHeader | BootRegistryHeaderLegacy,
) -> None:
    """Test getting entries of boot registry."""
    entries = boot_registry.get_entries()
    match boot_registry:
        case BootRegistryHeader():
            assert len(entries) == sum(  # count of total entries
                1
                for entry in boot_registry.entry
                if entry.value and not entry.next_block_present
            )
        case BootRegistryHeaderLegacy():
            assert len(entries) == len(
                boot_registry.entry.rstrip(b"\x00")
                .removesuffix(b"EOF\n")
                .strip()
                .splitlines()
            )
        case _:
            raise ValueError(
                f"Unknown boot registry header type '{type(boot_registry)}'"
            )


@pytest.mark.parametrize("random_string", [8, 64, 256], indirect=True)
def test_boot_registry_set_entries(
    boot_registry: BootRegistryHeader | BootRegistryHeaderLegacy,
    random_string: str,
) -> None:
    """Test setting entries of boot registry."""
    key = "key"
    value = random_string
    boot_registry.set_entry(key, value)
    assert key in boot_registry.get_entries()
    assert boot_registry.get_entries()[key] == value
