"""Collection of functions to assist other modules."""

import io
import subprocess

from igelfs.constants import IGF_SECTION_SHIFT, IGF_SECTION_SIZE


def get_start_of_section(index: int) -> int:
    """Return offset for start of section relative to image."""
    return index << IGF_SECTION_SHIFT


def get_section_of(offset: int) -> int:
    """Return section index for specified offset."""
    return offset >> IGF_SECTION_SHIFT


def get_offset_of(offset: int) -> int:
    """Return offset relative to start of section for specified offset."""
    return offset & (IGF_SECTION_SIZE - 1)


def replace_bytes(
    data: bytes, replacement: bytes, offset: int, strict: bool = True
) -> bytes:
    """
    Replace bytes at offset in data with replacement.

    If strict is True, ensure replacement will fit inside data.
    """
    if strict and len(replacement) > len(data) - offset:
        raise ValueError("Replacement does not fit inside data")
    with io.BytesIO(data) as fd:
        fd.seek(offset)
        fd.write(replacement)
        fd.seek(0)
        return fd.read()


def run_process(*args, **kwargs) -> str:
    """Run process and return stdout or raise exception if failed."""
    return (
        subprocess.run(
            *args,
            capture_output=kwargs.pop("capture_output", True),
            check=kwargs.pop("check", True),
            **kwargs,
        )
        .stdout.strip()
        .decode()
    )
