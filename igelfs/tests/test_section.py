"""Unit tests for a section."""

from igelfs.constants import IGF_SECT_DATA_LEN, IGF_SECT_HDR_LEN
from igelfs.models import Section


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
