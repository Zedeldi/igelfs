"""Unit tests for the hash block."""

from igelfs.constants import HASH_HDR_IDENT
from igelfs.models import Hash


def test_hash_header_verify(hash_: Hash) -> None:
    """Test verification of hash header."""
    assert hash_.header.verify()


def test_hash_header_magic(hash_: Hash) -> None:
    """Test ident attribute of hash header."""
    assert hash_.header.ident == HASH_HDR_IDENT


def test_hash_excludes_verify(hash_: Hash) -> None:
    """Test verification of hash excludes."""
    for exclude in hash_.excludes:
        assert exclude.verify()


def test_hash_signature(hash_: Hash) -> None:
    """Test verification of hash signature."""
    assert hash_.verify_signature()


def test_hash_excludes_count(hash_: Hash) -> None:
    """Test hash excludes size matches count in header."""
    assert hash_.header.count_excludes == len(hash_.excludes)


def test_hash_values_size(hash_: Hash) -> None:
    """Test hash values size matches header information."""
    assert (
        hash_.header.count_hash * hash_.header.hash_bytes
        == hash_.header.hash_block_size
        == len(hash_.values)
    )
