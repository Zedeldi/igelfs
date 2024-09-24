"""Testing configuration."""

import pytest

from igelfs.filesystem import Filesystem
from igelfs.models import BootRegistryHeader


def pytest_addoption(parser):
    """Parse command-line arguments."""
    parser.addoption("--path", action="store", default="default image path")


@pytest.fixture(scope="session")
def fs(pytestconfig) -> Filesystem:
    """Return Filesystem instance for image."""
    return Filesystem(pytestconfig.getoption("path"))


@pytest.fixture(scope="session")
def bootreg(fs: Filesystem) -> BootRegistryHeader:
    """Return BootRegistryHeader instance."""
    return fs.bootreg
