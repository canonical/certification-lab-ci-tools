#!/usr/bin/env python3

import datetime
import json
import os
import re
import subprocess

from influxdb import InfluxDBClient

INFLUX_HOST = "10.50.124.12"


client = InfluxDBClient(
    INFLUX_HOST, 8086, "ce", os.environ.get("INFLUX_PASS"), "desktopsnaps"
)


class CurlError(Exception):
    pass


def curl(url):
    cmd = ["curl", "-s", url]
    try:
        out = subprocess.check_output(cmd)
        return out.decode("utf-8")
    except subprocess.CalledProcessError:
        raise CurlError


def set_cause_version_from_manifest(cause, manifest):
    match = re.search(rf"^{cause}(?::\w+)?\s+([^\n]+)", manifest, re.MULTILINE)
    if match:
        return match.group(1).rstrip()
    else:
        return "N/A"


def set_cause_version_from_snap_list(cause, snap_list):
    match = re.search(rf"^{cause}\s+(\S+)\s+(\S+)\s+", snap_list, re.MULTILINE)
    if match:
        return f"{match.group(1)} ({match.group(2)})"
    else:
        return "N/A"


def main():
    build_url = os.getenv("BUILD_URL")
    print("BUILD_URL:", build_url)
    csv = ""
    try:
        with open("artifacts/checkbox.csv") as f:
            csv = f.read()
    except OSError:
        print("Unable to read CSV results.")
    print("CSV:", csv)
    if "snap,cold,hot" not in csv:
        raise SystemExit("CSV format unsupported")

    url = f"{build_url}api/json"
    try:
        res = curl(url)
    except CurlError:
        print("Unable to fetch jenkins project information.")
    build_desc = json.loads(res)
    print(json.dumps(build_desc, indent=4, sort_keys=True))
    cause = "Manual run"
    cause_version = "N/A"
    try:
        cause = build_desc["actions"][0]["causes"][0]["upstreamProject"]
        cause = (
            cause.replace("advocacy-trigger-", "")
            .replace("-snaps-baseline", "")
            .replace("-os-baseline", "")
        )
        cause = (
            cause.replace("-stable", "").replace("-candidate", "").replace("-beta", "")
        )
        try:
            with open("artifacts/snap_list.txt") as f:
                snap_list = f.read()
                cause_version = set_cause_version_from_snap_list(cause, snap_list)
        except OSError:
            snap_list = None
    except KeyError:
        try:
            cause_desc = build_desc["actions"][1]["causes"][0]["shortDescription"]
            if "URLTrigger" in cause_desc:
                res = curl(f"{build_url}triggerCauseAction/")
                m = re.search("The value for the JSON Path '(.*?)' has changed.", res)
                cause = m.group(1)
        except (KeyError, IndexError):
            print("failed to get build cause")
        except CurlError:
            print("Unable to fetch URLTrigger project information.")
        try:
            with open("artifacts/manifest.txt") as f:
                deb_manifest = f.read()
                cause_version = set_cause_version_from_manifest(cause, deb_manifest)
        except OSError:
            deb_manifest = None
    ts = build_desc["timestamp"]
    date = datetime.datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%dT%H:%M:%SZ")
    match = re.search(r"advocacy-(\w+)-(\w+)-gfx", os.getenv("JOB_NAME"))
    if match:
        release = match.groups()[0]
        hw_id = match.groups()[1]
    else:
        raise SystemExit("Unable to find release/hw_id data")

    snaps = {line.split(",")[0] for line in csv.splitlines()[1:]}
    for l in csv.splitlines()[1:]:
        try:
            snap, cold, hot = l.split(",")
            if hot == "-1":
                hot = 0
            if cold == "-1":
                cold = 0
            try:
                hot = float(hot)
            except ValueError:
                hot = 0.0
            try:
                cold = float(cold)
            except ValueError:
                cold = 0.0
            if cold == 0.0 or hot == 0.0:
                continue
            measurements = [
                {
                    "measurement": "startup_time",
                    "tags": {
                        "hw_id": hw_id,
                        "release": release,
                        "snap": snap,
                        "cause": cause,
                        "cause_version": cause_version,
                    },
                    "fields": {
                        "hot": hot,
                        "cold": cold,
                        "jenkins": f'<a href="{build_url}">Jenkins build</a>',
                    },
                    "time": date,
                }
            ]
            if cause in snaps and cause != snap:
                continue
            print("uploading measurements:", measurements)
            client.write_points(measurements)
        except ValueError:
            continue


if __name__ == "__main__":
    main()
