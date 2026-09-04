#!/usr/bin/env python3
"""
Get version and revision data for snaps we care about testing
"""

import json
import sys
from argparse import ArgumentParser

import requests
import yaml

parser = ArgumentParser()
parser.add_argument(
    "--config", "-c", required=True, help="Yaml file with snap names and store data"
)
args = parser.parse_args()

with open(args.config) as f:
    snap_data = yaml.safe_load(f)
    SNAPS = [(k, snap_data[k]["store"]) for k in snap_data.keys()]

"""
Create a yaml file that can be referenced like...
snap:
    track:
        risk:
            arch:
                version
                revision
"""
mysnapdict = dict()
for snap, store in SNAPS:
    url = f"https://api.snapcraft.io/v2/snaps/info/{snap}?fields=version,revision,snap-yaml"
    headers = {"Snap-Device-Series": "16", "Snap-Device-Store": store}
    a = requests.get(url, headers=headers)
    j = a.json()
    if not hasattr(mysnapdict, snap):
        mysnapdict[snap] = dict()
    if "channel-map" not in j:
        print("WARNING: BAD ITEM: ", file=sys.stderr)
        print(j, file=sys.stderr)
        continue
    for x in j.get("channel-map"):
        track = x["channel"]["track"]
        version = x["version"]
        revision = x["revision"]
        snap_yaml = x.get("snap-yaml")
        if snap_yaml:
            snap_dict = yaml.safe_load(snap_yaml)
            grade = snap_dict.get("grade")
        else:
            grade = "unknown"
        # Special case: We only want to test mir-kiosk for grade: stable
        if snap == "mir-kiosk" and grade == "devel":
            continue
        if track not in mysnapdict[snap]:
            mysnapdict[snap][track] = dict()
        risk = x["channel"]["risk"]
        if risk not in mysnapdict[snap][track]:
            mysnapdict[snap][track][risk] = dict()
        architecture = x["channel"]["architecture"]
        if architecture not in mysnapdict[snap][track][risk]:
            mysnapdict[snap][track][risk][architecture] = dict()
        mysnapdict[snap][track][risk][architecture]["version"] = version
        mysnapdict[snap][track][risk][architecture]["revision"] = revision
        mysnapdict[snap][track][risk][architecture]["grade"] = grade
print(json.dumps(mysnapdict, indent=2))
