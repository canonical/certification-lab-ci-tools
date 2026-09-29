#!/usr/bin/env python3
"""
Get version and revision data for snaps we care about testing
"""

import json
import sys
from argparse import ArgumentParser
from collections import defaultdict
from pathlib import Path

import requests
import yaml

# For these snaps ignore all non "stable" grade releases
SNAP_ONLY_STABLE_RELEASES = {"mir-kiosk"}


def parse_args():
    parser = ArgumentParser()
    parser.add_argument(
        "--config",
        "-c",
        required=True,
        help="Yaml file with snap names and store data",
        type=Path,
    )
    return parser.parse_args()


def snap_json_map_type():
    # snap json result is
    # { 'snap_name': { 'snap_track': { 'snap_risk': {
    #         'arch': {
    #           'version': ... (str)
    #           'revision:': ... (int)
    #           'grade': ... (stable/devel)
    #         } ...
    return defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))


def main():
    args = parse_args()

    with args.config.open("r") as f:
        snap_data = yaml.safe_load(f)
        snap_yaml = [(k, snap_data[k]["store"]) for k in snap_data]

    snap_json_map = snap_json_map_type()
    for name, store in snap_yaml:
        url = f"https://api.snapcraft.io/v2/snaps/info/{name}?fields=version,revision,snap-yaml"
        headers = {"Snap-Device-Series": "16", "Snap-Device-Store": store}
        store_response = requests.get(url, headers=headers)
        store_meta_json = store_response.json()
        if "channel-map" not in store_meta_json:
            print(f"WARNING: BAD ITEM:\n{store_meta_json}", file=sys.stderr)
            continue
        for meta in store_meta_json["channel-map"]:
            track = meta["channel"]["track"]
            risk = meta["channel"]["risk"]
            arch = meta["channel"]["architecture"]

            version = meta["version"]
            revision = meta["revision"]
            grade = yaml.safe_load(meta.get("snap-yaml", "grade: unknown")).get("grade")

            # Special case: We only want to test mir-kiosk for grade: stable
            if name in SNAP_ONLY_STABLE_RELEASES and grade != "stable":
                continue
            snap_json_map[name][track][risk][arch] = {
                "version": version,
                "revision": revision,
                "grade": grade,
            }

    print(json.dumps(snap_json_map, indent=2))


if __name__ == "__main__":
    main()
