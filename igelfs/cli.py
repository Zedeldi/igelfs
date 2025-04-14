"""Command-line interface for IGEL filesystem operations."""

import json
import logging
import sys
from argparse import ArgumentParser, Namespace
from pprint import pprint
from typing import Any

from igelfs.filesystem import Filesystem
from igelfs.lxos import FirmwareUpdate, LXOSParser
from igelfs.models import Section
from igelfs.registry import Registry

try:
    from igelfs.convert import Disk
except ImportError:
    _CONVERT_AVAILABLE = False
else:
    _CONVERT_AVAILABLE = True

try:
    from igelfs.kml import Keyring
except ImportError:
    _KEYRING_AVAILABLE = False
else:
    _KEYRING_AVAILABLE = True


def get_parser() -> ArgumentParser:
    """Return argument parser instance."""
    parser = ArgumentParser(
        prog="igelfs",
        description="Python implementation of the IGEL filesystem",
        epilog="Copyright (C) 2025 Zack Didcott",
    )
    subparsers = parser.add_subparsers(
        dest="command", help="action to perform", required=True
    )

    parser_info = subparsers.add_parser(
        "info", help="display information about filesystem"
    )
    parser_info.add_argument(
        "--section-count", "-s", action="store_true", help="get section count"
    )
    parser_info.add_argument(
        "--json", "-j", action="store_true", help="format result as JSON"
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
    parser_add.add_argument("--type", "-t", type=int, help="partition type")
    parser_add.add_argument(
        "--as-partition",
        "-p",
        action="store_true",
        help="use file as a partition directly",
    )
    parser_remove = subparsers.add_parser(
        "remove", help="remove partition from filesystem"
    )
    parser_remove.add_argument("minor", type=int, help="partition minor")
    parser_boot_registry = subparsers.add_parser(
        "boot-registry", help="manage boot registry of filesystem"
    )
    parser_boot_registry_subparsers = parser_boot_registry.add_subparsers(
        dest="action", help="action to perform for boot registry", required=True
    )
    parser_boot_registry_get = parser_boot_registry_subparsers.add_parser(
        "get", help="get value from boot registry"
    )
    parser_boot_registry_get.add_argument("--key", "-k", help="key to get")
    parser_boot_registry_get.add_argument(
        "--json", "-j", action="store_true", help="format result as JSON"
    )
    parser_boot_registry_set = parser_boot_registry_subparsers.add_parser(
        "set", help="set key to value in boot registry"
    )
    parser_boot_registry_set.add_argument("key", help="key to set")
    parser_boot_registry_set.add_argument("value", help="value to set")
    parser_registry = subparsers.add_parser(
        "registry", help="manage registry of filesystem"
    )
    parser_registry_subparsers = parser_registry.add_subparsers(
        dest="action", help="action to perform for registry", required=True
    )
    parser_registry_get = parser_registry_subparsers.add_parser(
        "get", help="get value from registry"
    )
    parser_registry_get.add_argument("--key", "-k", help="key to get")
    parser_registry_get.add_argument(
        "--decrypt", "-d", action="store_true", help="decrypt value"
    )
    parser_registry_get.add_argument(
        "--json", "-j", action="store_true", help="format result as JSON"
    )
    parser_keys = subparsers.add_parser(
        "keys", help="manage filesystem encryption keys"
    )
    parser_keys.add_argument(
        "name", help="key name, e.g. 'extent-key', 'master-key', '255'"
    )
    parser_keys.add_argument(
        "--hex", "-H", action="store_true", help="output key as hexadecimal"
    )
    parser_keys.add_argument("--output", "-o", help="write key to file")
    parser_update = subparsers.add_parser(
        "update", help="update filesystem with firmware archive"
    )
    parser_update.add_argument("firmware", help="path to firmware archive")
    parser_rebuild = subparsers.add_parser(
        "rebuild", help="rebuild filesystem to new image"
    )
    parser_rebuild.add_argument("output", help="path to write rebuilt filesystem")
    subparsers.add_parser("clean", help="clean unused sections in filesystem")
    parser_extract = subparsers.add_parser(
        "extract", help="dump all filesystem content"
    )
    parser_extract.add_argument(
        "--partitions", "-p", help="list of partitions to extract, e.g. 1,2,250-255"
    )
    parser_extract.add_argument(
        "directory", help="destination directory for extraction"
    )
    parser_convert = subparsers.add_parser(
        "convert", help="convert filesystem to GPT partitioned disk"
    )
    parser_convert.add_argument("output", help="path to write GPT disk")

    parser.add_argument("--inf", help="path to lxos.inf configuration file")
    parser.add_argument(
        "-l",
        "--log-level",
        default=logging.WARNING,
        choices=logging.getLevelNamesMapping().keys(),
        type=str.upper,
        help="Set log level",
    )
    parser.add_argument("path", help="path to the IGEL filesystem image")
    return parser


def check_args(args: Namespace) -> None:
    """Check sanity of parsed arguments."""
    if (args.command in ("keys", "registry") and not _KEYRING_AVAILABLE) or (
        args.command == "convert" and not _CONVERT_AVAILABLE
    ):
        print(f"Command '{args.command}' is not available.")
        sys.exit(1)
    if args.command == "registry" and args.decrypt and not args.key:
        print("Key must be set when decrypting registry value")
        sys.exit(1)
    if args.command == "add" and args.type and args.as_partition:
        print("Type has no effect when file is used as partition")
        sys.exit(1)


def main() -> None:
    """Parse arguments and perform specified command."""
    parser = get_parser()
    args = parser.parse_args()
    check_args(args)
    logging.basicConfig(
        format="%(asctime)s | [%(levelname)s] %(message)s", level=args.log_level
    )

    filesystem = Filesystem(args.path)
    lxos_config = LXOSParser(args.inf) if args.inf else None
    match args.command:
        case "new":
            Filesystem.new(args.path, args.size)
        case "add":
            if args.as_partition:
                with open(args.input, "rb") as file:
                    data = file.read()
                sections = Section.from_bytes_to_collection(data)
            else:
                opts = {}
                if args.type:
                    opts["type_"] = args.type
                sections = Filesystem.create_partition_from_file(args.input, **opts)
            filesystem.write_partition(sections, args.minor)
        case "remove":
            filesystem.delete_partition(args.minor)
        case "boot-registry":
            match args.action:
                case "get":
                    entries = filesystem.boot_registry.get_entries()
                    # boot_id is not stored as an entry for structured headers
                    entries["boot_id"] = filesystem.boot_registry.get_boot_id()
                    value = {args.key: entries.get(args.key)} if args.key else entries
                    if args.json:
                        print(json.dumps(value))
                    else:
                        pprint(value.get(args.key) if args.key else value)
                case "set":
                    boot_registry = filesystem.boot_registry
                    boot_registry.set_entry(args.key, args.value)
                    filesystem.write_boot_registry(boot_registry)
        case "registry":
            match args.action:
                case "get":
                    registry = Registry.from_filesystem(filesystem)
                    registry_value = (
                        {
                            args.key: (
                                registry.get_crypt(args.key)
                                if args.decrypt
                                else registry.get(args.key)
                            )
                        }
                        if args.key
                        else registry.to_dict()
                    )
                    if args.json:
                        print(json.dumps(registry_value))
                    else:
                        pprint(
                            registry_value.get(args.key) if args.key else registry_value
                        )
        case "keys":
            keyring = Keyring.from_filesystem(filesystem)
            match args.name:
                case "extent-key":
                    key = keyring.extent_key
                case "master-key":
                    key = keyring.master_key
                case name:
                    key = keyring.get_key(name)
            if path := args.output:
                with open(path, "wb") as file:
                    file.write(key)
            print(key.hex() if args.hex else key)
        case "update":
            firmware = FirmwareUpdate(args.firmware)
            filesystem.update(firmware)
        case "rebuild":
            filesystem.rebuild(args.output)
        case "clean":
            filesystem.clean()
        case "extract":
            partition_minors: list[int] = []
            if args.partitions:
                for partition in args.partitions.split(","):
                    partition = partition.strip()
                    if "-" in partition:
                        start, end = map(int, partition.split("-"))
                        partition_minors.extend(range(start, end + 1))
                    else:
                        partition_minors.append(int(partition))
            filesystem.extract_to(
                args.directory,
                partition_minors=partition_minors,
                lxos_config=lxos_config,
            )
        case "convert":
            Disk.from_filesystem(args.output, filesystem, lxos_config)
        case "info":
            info: Any
            if args.section_count:
                if args.json:
                    info = {"section_count": filesystem.section_count}
                else:
                    info = filesystem.section_count
            else:
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
