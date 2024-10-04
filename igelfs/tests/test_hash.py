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
