#!/usr/bin/env python3
"""
This script is meant to query the store to get the latest version published
of a given snap

Example invocation:
    $ python3 get_latest_snap_published.py checkbox beta
    v3.1.2-dev20
"""

import sys
from argparse import ArgumentParser

from snap_info_utility import get_snap_info_from_store


def parse_args(argv):
    parser = ArgumentParser()
    parser.add_argument("snap_name", help="Name of the snap")
    parser.add_argument(
        "channel",
        choices=["edge", "beta", "candidate", "stable"],
        help="Channel to get the snap from",
    )

    return parser.parse_args(argv)


def get_latest_version(snap_info, channel):
    for entry in snap_info["channel-map"]:
        if entry["channel"]["name"] == channel:
            return entry["version"]
    raise SystemExit("No version found in the specified channel")


def get_snap_store_version(snap_name: str, channel: str) -> str:
    """
    Returns the latest available version of the snap in a given channel
    """
    snap_info = get_snap_info_from_store(snap_name)

    return get_latest_version(snap_info, channel)


def main(argv):
    args = parse_args(argv)
    version = get_snap_store_version(args.snap_name, args.channel)
    print(version)


if __name__ == "__main__":
    main(sys.argv[1:])
