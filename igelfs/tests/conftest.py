"""Testing configuration."""

import random

import pytest

from igelfs.filesystem import Filesystem
from igelfs.models import BootRegistryHeader, Directory, Section


def pytest_addoption(parser):
    """Parse command-line arguments."""
    parser.addoption("--path", action="store", default="default image path")


@pytest.fixture(scope="session")
def fs(pytestconfig) -> Filesystem:
    """Return Filesystem instance for image."""
    return Filesystem(pytestconfig.getoption("path"))


@pytest.fixture(scope="session")
def boot_registry(fs: Filesystem) -> BootRegistryHeader:
    """Return BootRegistryHeader instance."""
    return fs.boot_registry


@pytest.fixture(scope="session")
def directory(fs: Filesystem) -> Directory:
    """Return Directory instance."""
    return fs.directory


@pytest.fixture()
def section(fs: Filesystem) -> Section:
    """Return random Section instance (excluding section #0 and last section)."""
    return fs[random.randint(1, fs.section_count - 1)]
