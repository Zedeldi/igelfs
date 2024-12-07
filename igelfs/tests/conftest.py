"""Testing configuration."""

import random
import string

import pytest

from igelfs.filesystem import Filesystem
from igelfs.lxos import LXOSParser
from igelfs.models import (
    BootRegistryHeader,
    BootRegistryHeaderLegacy,
    DataModelCollection,
    Directory,
    Hash,
    Section,
)

SKIP_PARTITION_MINORS = (238, 239, 241, 242, 243, 245, 247, 248, 252, 253, 254, 255)


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
    skip_inf = pytest.mark.skip(reason="Firmware information file not provided")
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
    return LXOSParser(path=pytestconfig.getoption("inf"))


@pytest.fixture(scope="session")
def boot_registry(
    filesystem: Filesystem,
) -> BootRegistryHeader | BootRegistryHeaderLegacy:
    """Return BootRegistryHeader or BootRegistryHeaderLegacy instance."""
    return filesystem.boot_registry


@pytest.fixture(scope="session")
def directory(filesystem: Filesystem) -> Directory:
    """Return Directory instance."""
    return filesystem.directory


@pytest.fixture()
def section(filesystem: Filesystem) -> Section:
    """Return random Section instance from filesystem."""
    section = None
    while not section:
        try:
            section = filesystem[random.randint(1, filesystem.section_count)]
        except ValueError:
            continue
        if section.header.partition_minor in SKIP_PARTITION_MINORS:
            section = None
    return section


@pytest.fixture(scope="session")  # scope="session" as static across tests
def hash_(filesystem: Filesystem) -> Hash:
    """Return first Hash instance from filesystem."""
    for section in filesystem:
        if section.hash:
            return section.hash
    else:
        pytest.skip("No hashes found")


@pytest.fixture(scope="session")
def sys(filesystem: Filesystem) -> DataModelCollection[Section]:
    """Return sys Section instances from filesystem."""
    return filesystem.find_sections_by_directory(1)


@pytest.fixture(scope="session")
def bspl(filesystem: Filesystem) -> DataModelCollection[Section]:
    """Return bspl Section instances from filesystem."""
    return filesystem.find_sections_by_directory(23)


@pytest.fixture()
def random_string(request: pytest.FixtureRequest) -> str:
    """Return random string of specified length."""
    return "".join(random.choice(string.ascii_lowercase) for _ in range(request.param))
