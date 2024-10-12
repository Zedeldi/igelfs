"""Collection of functions to assist other modules."""

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
