#!/usr/bin/env python3
# Copyright (C) 2018-2022 Canonical Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Written by:
#       Maciej Kisielewski <maciej.kisielewski@canonical.com>
import argparse
import json
import os
import re
import time

from influx_credentials import credentials

"""
Extract job timing information from a submission file and push it to the
influxDB.

For jobs listed in MEASURED_JOBS take 'duration' field as reported by Checkbox.
For job specified by BOOTUP_JOB_ID parse the jobs output in search for
systemd-analyze output and use that as the measurement.

After measurements are extracted, they are pushed to the influxDB specified
in the influx_credentials.py.
"""

MEASURED_JOBS = [
    "snap-install",
    "snap-remove",
    "connect-tillamook-plugs",
    "connect-caracalla-plugs",
]

BOOTUP_JOB_ID = "info/systemd-analyze"


def dquote(s):
    # surround s with double quotes
    return '"{}"'.format(s)


def to_human_name(hw_id):
    better_names = {
        "cert-caracalla-transport-checkbox-plano-edge": "Caracalla plano-edge",
        "cert-tillamook-core-beta": "Tillamook core beta",
        "cert-cm3-core-beta": "CM3 core-beta",
    }
    return better_names.get(hw_id, hw_id)


class InfluxQueryWriter:
    def __init__(self, hw_id, submission, tstamp=None):
        self._proj = dquote(submission.get("title", "unknown"))
        self._time = int(tstamp * 10**9)
        self._hw_id = dquote(to_human_name(hw_id))
        self._os_kind = dquote(
            submission.get("distribution", dict()).get("description", "unknown")
        )
        snap_packages = submission.get("snap-packages", dict())
        for snap in snap_packages:
            if snap.get("name", "") == "core":
                self._core_rev = snap.get("revision", "0")
                break
        else:
            self._core_rev = "0"
        self._results = submission.get("results", []) + submission.get(
            "resource-results", []
        )

    def generate_sql_inserts(self):
        TMPL = (
            "INSERT snap_timing,project_name={proj},job_name={job},"
            "hw_id={hw},os_kind={os},core_revision={core_rev} "
            "elapsed={elapsed} {tstamp}"
        )
        for m in self.extract_measurements():
            yield TMPL.format(
                proj=m["tags"]["project_name"],
                job=m["tags"]["job_name"],
                hw=m["tags"]["hw_id"],
                os=m["tags"]["os_kind"],
                core_rev=m["tags"]["core_revision"],
                elapsed=m["fields"]["elapsed"],
                tstamp=m["time"],
            )

    def extract_measurements(self):
        for result in self._results:
            # for some jobs extract elapsed time as measured by checkbox
            for job in MEASURED_JOBS:
                if result["id"].endswith(job):
                    if not result.get("duration"):
                        continue
                    measurement = {
                        "measurement": "snap_timing",
                        "tags": {
                            "project_name": self._proj,
                            "job_name": dquote(job),
                            "hw_id": self._hw_id,
                            "os_kind": self._os_kind,
                            "core_revision": self._core_rev,
                        },
                        "time": self._time,
                        "fields": {
                            "elapsed": result["duration"],
                        },
                    }
                    yield measurement
            # for boot-up job extract time from the job's output
            if result["id"].endswith(BOOTUP_JOB_ID):
                timings = parse_sysd_analyze(result["io_log"])
                if "total" not in timings.keys():
                    print(
                        "{} job didn't have proper output. It returned:\n{}".format(
                            result["id"], result["io_log"]
                        )
                    )
                else:
                    measurement = {
                        "measurement": "snap_timing",
                        "tags": {
                            "project_name": self._proj,
                            "job_name": dquote(BOOTUP_JOB_ID),
                            "hw_id": self._hw_id,
                            "os_kind": self._os_kind,
                            "core_revision": self._core_rev,
                        },
                        "time": self._time,
                        "fields": {
                            "elapsed": timings["total"],
                        },
                    }
                    yield measurement


def parse_sysd_analyze(text):
    """
    >>> expected = {'kernel': 5.459, 'userspace': 18.985, 'total': 24.444}
    >>> parse_sysd_analyze('Startup finished in 5.459s (kernel)'
    ... '+ 18.985s (userspace) = 24.444s') == {
    ... 'kernel': 5.459, 'userspace': 18.985, 'total': 24.444}
    True
    >>> parse_sysd_analyze('Weird output')
    >>> parse_sysd_analyze('Startup finished in 5.459s (kernel)'
    ... '+ 2min 18.985s (userspace) = 2min 24.444s') == {
    ... 'kernel': 5.459, 'userspace': 138.985, 'total': 144.444}
    True
    >>> parse_sysd_analyze('Startup finished in 1min 36.935s (kernel)'
    ... '+ 1min 42.338s (userspace) = 3min 19.273s') == {
    ... 'kernel': 96.935, 'userspace': 102.338, 'total': 199.273}
    True
    >>> parse_sysd_analyze('Startup finihsed in 1h 4min 20.111s (kernel)'
    ... '+ 2h 2min 30.222s (userspace) = 3h 6min 50.333s') == {
    ... 'kernel': 3860.111, 'userspace': 7350.222, 'total': 11210.333}
    True
    >>> parse_sysd_analyze('Startup finished in 5s (kernel)'
    ... '+ 4s (userspace) = 9s') == {
    ... 'kernel': 5.0, 'userspace': 4.0, 'total': 9.0}
    True
    >>> parse_sysd_analyze('Startup finished in 18.420s (firmware)'
    ... '+ 18.034s (loader) + 10.429s (kernel) + 38.353s (userspace)'
    ... '= 1min 25.239s') == {
    ... 'firmware': 18.420, 'loader': 18.034, 'kernel': 10.429,
    ... 'userspace': 38.353, 'total': 85.239}
    True
    >>> parse_sysd_analyze('Startup finished in 17.105s (firmware)'
    ... '+ 18.256s (loader) + 11.252s (kernel) + 1min 14.137s (userspace)'
    ... '= 2min 752ms') == {
    ... 'firmware': 17.105, 'loader': 18.256, 'kernel': 11.252,
    ... 'userspace': 74.137, 'total': 120.752}
    True
    """
    if "+" not in text or "=" not in text:
        return

    def extract(tx):
        # XXX: fractions of a seconds can be printed in two ways depending if
        # there are whole seconds to report
        RE = (
            r"[^\d]*(?P<hours>\s?\d+h)?(?P<minutes>\s?\d+min)?"
            "(?P<seconds>\s?\d+(\.\d*)?s)?(?P<millis>\s?\d+ms)?"
        )
        groups = re.match(RE, tx).groupdict()
        hours = (groups["hours"] or "0h")[:-1]
        minutes = (groups["minutes"] or "0min")[:-3]
        seconds = (groups["seconds"] or "0s")[:-1]
        milliseconds = (groups["millis"] or "0ms")[:-2]
        res = (
            float(hours) * 3600
            + float(minutes) * 60
            + float(seconds)
            + float(milliseconds) / 1000
        )
        return res

    head, tail = text.split("=")
    res = {"total": extract(tail)}
    segments = head.split("+")
    for seg in segments:
        label = re.search(r"\((.+)\)", seg).groups()[0]
        res[label] = extract(seg)
    return res


def push_to_influx(measurements):
    from influxdb import InfluxDBClient

    client = InfluxDBClient(
        credentials["host"],
        8086,
        credentials["user"],
        os.environ.get("INFLUX_PASS") or credentials["pass"],
        credentials["dbname"],
    )
    client.write_points(measurements)


def push_using_bridge(measurements):
    import requests

    reqobj = {"database": "snappy_performance", "measurements": list(measurements)}
    res = requests.post("http://10.101.51.246:8000/influx", json=reqobj)
    return res


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("SUBMISSION_FILE")
    parser.add_argument("--hw_id", default="unknown")
    parser.add_argument("--timestamp", default=time.time(), type=float)
    parser.add_argument(
        "--sql",
        action="store_true",
        help=("Print out insert queries instead of pushing object to influx"),
    )
    parser.add_argument(
        "--bridge", action="store_true", help=("Use bridge to push measurements")
    )
    args = parser.parse_args()

    try:
        with open(args.SUBMISSION_FILE, "rt") as f:
            try:
                content = json.load(f)
            except json.JSONDecodeError:
                raise SystemExit("Failed to parse {}".format(args.SUBMISSION_FILE))
            iqw = InfluxQueryWriter(args.hw_id, content, args.timestamp)
            if args.sql:
                print("\n".join(iqw.generate_sql_inserts()))
            elif args.bridge:
                return push_using_bridge(iqw.extract_measurements())
            else:
                push_to_influx(iqw.extract_measurements())
    except Exception as exc:
        raise exc


if __name__ == "__main__":
    main()
