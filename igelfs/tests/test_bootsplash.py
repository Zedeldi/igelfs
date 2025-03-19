"""Unit tests for the bootsplash models."""

import pytest

from igelfs.constants import BOOTSPLASH_MAGIC, ExtentType
from igelfs.models import (
    BootsplashExtent,
    BootsplashHeader,
    DataModelCollection,
    Partition,
    Section,
)


def test_bootsplash_magic(bspl: DataModelCollection[Section]) -> None:
    """Test magic string attribute of bootsplash header."""
    header = BootsplashHeader.from_bytes(bspl[0].data)
    assert header.magic == BOOTSPLASH_MAGIC


def test_bspl_splash_extent(bspl: DataModelCollection[Section]) -> None:
    """Test getting splash extent from bootsplash sections."""
    partition = bspl[0].partition
    assert isinstance(partition, Partition)
    for extent in partition.extents:
        # UDC and OSC ISOs store splash extents as type KERNEL
        if extent.get_type() in (ExtentType.SPLASH, ExtentType.KERNEL):
            break
    else:
        pytest.skip("Bootsplash partition does not have a splash extent")
    data = Section.get_extent_of(bspl, extent)
    splash = BootsplashExtent.from_bytes(data)
    assert len(splash.get_images()) == len(splash.splashes) == splash.header.num_splashs
