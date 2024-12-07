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
    subparsers = parser.add_subparsers(
        dest="command", help="action to perform", required=True
    )

    parser_info = subparsers.add_parser(
        "info", help="display information about filesystem"
    )
    parser_info.add_argument(
        "--json", action="store_true", help="format result as JSON"
    )
    parser_new = subparsers.add_parser("new", help="create a new filesystem")
    parser_new.add_argument(
        "size", type=int, help="size of the new filesystem in sections"
    )
    parser_add = subparsers.add_parser(
        "add", help="add file as partition to filesystem"
    )
    parser_add.add_argument("input", help="path to file for partition")
    parser_add.add_argument("minor", type=int, help="partition minor")
    parser_add.add_argument("--type", type=int, help="partition type")
    parser_rebuild = subparsers.add_parser(
        "rebuild", help="rebuild filesystem to new image"
    )
    parser_rebuild.add_argument("output", help="path to write rebuilt filesystem")
    parser_extract = subparsers.add_parser(
        "extract", help="dump all filesystem content"
    )
    parser_extract.add_argument(
        "directory", help="destination directory for extraction"
    )
    parser_convert = subparsers.add_parser(
        "convert", help="convert filesystem to GPT partitioned disk"
    )
    parser_convert.add_argument("output", help="path to write GPT disk")

    parser.add_argument("--inf", help="path to lxos.inf configuration file")
    parser.add_argument("path", help="path to the IGEL filesystem image")
    return parser


def check_args(args: Namespace) -> None:
    """Check sanity of parsed arguments."""
    if args.command == "convert" and not CONVERT_AVAILABLE:
        print("Filesystem conversion is not available.")
        sys.exit(1)


def main() -> None:
    """Parse arguments and print filesystem information."""
    parser = get_parser()
    args = parser.parse_args()
    check_args(args)
    filesystem = Filesystem(args.path)
    lxos_config = LXOSParser(args.inf) if args.inf else None
    match args.command:
        case "new":
            Filesystem.new(args.path, args.size)
        case "add":
            opts = {}
            if args.type:
                opts["type_"] = args.type
            sections = Filesystem.create_partition_from_file(args.input, **opts)
            filesystem.write_partition(sections, args.minor)
        case "rebuild":
            filesystem.rebuild(args.output)
        case "extract":
            filesystem.extract_to(args.directory, lxos_config)
        case "convert":
            Disk.from_filesystem(args.output, filesystem, lxos_config)
        case "info":
            info = filesystem.get_info(lxos_config)
            if args.json:
                print(json.dumps(info))
            else:
                pprint(info)
        case _:
            # argparse should catch this, so do not handle gracefully
            raise ValueError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
