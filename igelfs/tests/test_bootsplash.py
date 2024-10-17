"""Unit tests for the bootsplash models."""

import pytest

from igelfs.constants import BOOTSPLASH_MAGIC, ExtentType
from igelfs.models import (
    BootsplashExtent,
    BootsplashHeader,
    DataModelCollection,
    Section,
)


def test_bootsplash_magic(bspl: DataModelCollection[Section]) -> None:
    """Test magic string attribute of bootsplash header."""
    header = BootsplashHeader.from_bytes(bspl[0].data)
    assert header.magic == BOOTSPLASH_MAGIC


def test_bspl_splash_extent(bspl: DataModelCollection[Section]) -> None:
    """Test getting splash extent from bootsplash sections."""
    for extent in bspl[0].partition.extents:
        if extent.get_type() == ExtentType.SPLASH:
            break
    else:
        raise ValueError("Bootsplash partition does not have a splash extent")
    splash = Section.get_extent_of(bspl, extent)
    extent = BootsplashExtent.from_bytes(splash)
    assert len(extent.get_images()) == len(extent.splashes) == extent.header.num_splashs
