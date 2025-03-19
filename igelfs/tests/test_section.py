"""Unit tests for a section."""

import magic
import pytest

from igelfs.constants import IGF_SECT_DATA_LEN, IGF_SECT_HDR_LEN, ExtentType
from igelfs.models import DataModelCollection, Partition, Section


def test_section_size(section: Section) -> None:
    """Test size of section."""
    size = section.get_actual_size()
    assert size == section.get_model_size()
    assert size == IGF_SECT_HDR_LEN + IGF_SECT_DATA_LEN


def test_section_header_size(section: Section) -> None:
    """Test size of section header."""
    size = section.header.get_actual_size()
    assert size == section.header.get_model_size()
    assert size == IGF_SECT_HDR_LEN


def test_section_data_size(section: Section) -> None:
    """Test size of section data."""
    size = section.get_actual_size() - section.header.get_actual_size()
    assert size == IGF_SECT_DATA_LEN


def test_section_verify(section: Section) -> None:
    """Test verification of section."""
    assert section.verify()


def test_section_payload(sys: DataModelCollection[Section]) -> None:
    """Test getting payloads of section."""
    partition = sys[0].partition
    assert isinstance(partition, Partition)
    data = Section.get_payload_of(sys)  # sys partition has kernel extent
    data_with_extents = Section.get_payload_of(sys, include_extents=True)
    extents = [Section.get_extent_of(sys, extent) for extent in partition.extents]
    # Legacy filesystems (<= OS 10) do not have hash blocks
    hash_size = hash_.get_actual_size() if (hash_ := sys[0].hash) else 0
    assert len(data) + sum(len(extent) for extent in extents) == len(data_with_extents)
    assert (  # start of actual payload
        partition.get_actual_size() + hash_size + partition.get_extents_length()
        == partition.header.offset_blocks
    )


def test_sys_kernel_extent(sys: DataModelCollection[Section]) -> None:
    """Test getting kernel extent from system sections."""
    partition = sys[0].partition
    assert isinstance(partition, Partition)
    for extent in partition.extents:
        if extent.get_type() == ExtentType.KERNEL:
            break
    else:
        # UDC and OSC ISOs store kernel as a separate bzImage file
        pytest.skip("System partition does not have a kernel extent")
    kernel = Section.get_extent_of(sys, extent)
    assert "Linux kernel" in magic.from_buffer(kernel)
