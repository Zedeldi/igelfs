"""Testing configuration."""

import random

import pytest

from igelfs.filesystem import Filesystem
from igelfs.models import BootRegistryHeader, Section


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


@pytest.fixture()
def section(fs: Filesystem) -> Section:
    """Return random Section instance (excluding section #0)."""
    return fs[random.randint(1, 100)]
