"""Command-line interface for IGEL filesystem operations."""

import json
from argparse import ArgumentParser
from pprint import pprint

from igelfs.filesystem import Filesystem
from igelfs.lxos import LXOSParser


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
    return parser


def main() -> None:
    """Parse arguments and print filesystem information."""
    parser = get_parser()
    args = parser.parse_args()
    filesystem = Filesystem(args.path)
    lxos_config = LXOSParser(args.inf) if args.inf else None
    info = filesystem.get_info(lxos_config)
    if args.json:
        print(json.dumps(info))
    else:
        pprint(info)


if __name__ == "__main__":
    main()
