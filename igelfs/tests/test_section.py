"""Unit tests for a section."""

from igelfs.constants import IGF_SECT_DATA_LEN, IGF_SECT_HDR_LEN
from igelfs.models import DataModelCollection, Section


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
    data = Section.get_payload_of(sys)  # sys partition has kernel extent
    data_with_extents = Section.get_payload_of(sys, include_extents=True)
    extents = [
        Section.get_extent_of(sys, extent) for extent in sys[0].partition.extents
    ]
    assert len(data) + sum(len(extent) for extent in extents) == len(data_with_extents)
