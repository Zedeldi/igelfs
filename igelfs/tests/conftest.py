"""Testing configuration."""

import random

import pytest

from igelfs.filesystem import Filesystem
from igelfs.lxos import LXOSParser
from igelfs.models import BootRegistryHeader, Directory, Hash, Section


def pytest_addoption(parser):
    """Parse command-line arguments."""
    parser.addoption(
        "--image", action="store", help="path to filesystem image", required=True
    )
    parser.addoption("--inf", action="store", help="path to LXOS configuration file")


def pytest_collection_modifyitems(config, items):
    """Configure tests based on parsed arguments."""
    if config.getoption("inf"):
        return
    skip_inf = pytest.mark.skip(reason="firmware information file not provided")
    for item in items:
        if "inf" in item.keywords:
            item.add_marker(skip_inf)


@pytest.fixture(scope="session")
def filesystem(pytestconfig) -> Filesystem:
    """Return Filesystem instance for image."""
    return Filesystem(pytestconfig.getoption("image"))


@pytest.fixture(scope="session")
def parser(pytestconfig) -> LXOSParser:
    """Return configuration parser for LXOS files."""
    parser = LXOSParser()
    parser.read(pytestconfig.getoption("inf"))
    return parser


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
