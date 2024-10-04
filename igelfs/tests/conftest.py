"""Testing configuration."""

import random

import pytest

from igelfs.filesystem import Filesystem
from igelfs.models import BootRegistryHeader, Directory, Hash, Section


def pytest_addoption(parser):
    """Parse command-line arguments."""
    parser.addoption("--path", action="store", default="default image path")


@pytest.fixture(scope="session")
def filesystem(pytestconfig) -> Filesystem:
    """Return Filesystem instance for image."""
    return Filesystem(pytestconfig.getoption("path"))


@pytest.fixture(scope="session")
def boot_registry(filesystem: Filesystem) -> BootRegistryHeader:
    """Return BootRegistryHeader instance."""
    return filesystem.boot_registry


@pytest.fixture(scope="session")
def directory(filesystem: Filesystem) -> Directory:
    """Return Directory instance."""
    return filesystem.directory


@pytest.fixture()
def section(filesystem: Filesystem) -> Section:
    """Return random Section instance from filesystem."""
    return filesystem[random.choice(filesystem.valid_sections)]


@pytest.fixture()
def hash_(filesystem: Filesystem) -> Hash:
    """Return first Hash instance from filesystem."""
    return filesystem[1].hash
