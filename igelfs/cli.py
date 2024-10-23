"""Command-line interface for IGEL filesystem operations."""

import json
import sys
from argparse import ArgumentParser, Namespace
from pprint import pprint

from igelfs.filesystem import Filesystem
from igelfs.lxos import LXOSParser

try:
    from igelfs.convert import Disk
except ImportError:
    CONVERT_AVAILABLE = False
else:
    CONVERT_AVAILABLE = True


def get_parser() -> ArgumentParser:
    """Return argument parser instance."""
    parser = ArgumentParser(
        prog="igelfs",
        description="Python implementation of the IGEL filesystem",
        epilog="Copyright (C) 2024 Zack Didcott",
    )
    parser.add_argument("path", help="path to the IGEL filesystem image")
    parser.add_argument("--inf", help="path to lxos.inf configuration file")
    parser.add_argument("--json", action="store_true", help="format result as JSON")
    parser.add_argument("--extract", help="path to dump all filesystem content")
    parser.add_argument(
        "--convert", help="path for converting filesystem to GPT partitioned disk"
    )
    return parser


def check_args(args: Namespace) -> None:
    """Check sanity of parsed arguments."""
    if args.convert and not CONVERT_AVAILABLE:
        print("Filesystem conversion is not available.")
        sys.exit(1)


def main() -> None:
    """Parse arguments and print filesystem information."""
    parser = get_parser()
    args = parser.parse_args()
    check_args(args)
    filesystem = Filesystem(args.path)
    lxos_config = LXOSParser(args.inf) if args.inf else None
    if args.extract:
        filesystem.extract_to(args.extract, lxos_config)
    if args.convert:
        Disk.from_filesystem(args.convert, filesystem, lxos_config)
    info = filesystem.get_info(lxos_config)
    if args.json:
        print(json.dumps(info))
    else:
        pprint(info)


if __name__ == "__main__":
    main()
