#!/usr/bin/env python3
#
# Copyright (C) 2020 Canonical Ltd
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
#        Chris Wayne <cwayne@ubuntu.com>

import os

import requests
from dateutil import parser
from influxdb import InfluxDBClient

INFLUX_HOST = "10.50.124.12"


def init_influx():
    """Init influxdb with policy"""
    dbname = "pre-certs-report"
    client = InfluxDBClient(
        INFLUX_HOST, 8086, "ce", os.environ.get("INFLUX_PASS"), dbname
    )
    dbs = client.get_list_database()
    if {"name": dbname} not in dbs:
        client.create_database(dbname)
        client.create_retention_policy("default_policy", "350w", 1, default=True)


def push_influx_generic(measurement, tags, time, fields):
    """Generic influx measurement pusher"""
    dbname = "pre-certs-report"
    client = InfluxDBClient(
        INFLUX_HOST, 8086, "ce", os.environ.get("INFLUX_PASS"), dbname
    )

    body = [{"measurement": measurement, "tags": tags, "time": time, "fields": fields}]
    client.write_points(body)
    print(f"Measurement pushed to influx at {time}")


def main():
    print("Initialize influx")
    init_influx()
    print("Influx initialized")
    # request a report of all the certificates issued
    url = "https://certification.canonical.com/api/v1/certifiedmodeldetails/report/?format=json"
    r = requests.get(url)
    if not r.ok:
        raise SystemExit(f"Unable to access report. HTTP {r.status_code}")
    report = r.json()
    measure = "pre-certs-report"

    for cert in report["certificates"]:
        tags = dict()
        fields = dict()
        tags["model"] = cert["model"]
        tags["network"] = cert["network"]
        tags["wireless"] = cert["wireless"]
        tags["kernel_version"] = cert["kernel_version"]
        tags["processor"] = cert["processor"]
        tags["release"] = cert["certified_release"]
        tags["video"] = cert["video"]
        tags["make"] = cert["make"]
        tags["level"] = cert["level"]
        fields["wireless"] = cert["wireless"]
        fields["level"] = cert["level"]
        fields["model"] = cert["model"]
        fields["video"] = cert["video"]
        fields["network"] = cert["network"]
        fields["processor"] = cert["processor"]
        fields["kernel_version"] = cert["kernel_version"]
        fields["make"] = cert["make"]
        fields["certified_release"] = cert["certified_release"]
        fields["certified"] = 1
        completed_date = parser.parse(cert["completed"]).replace(tzinfo=None)
        ts = completed_date.timestamp() * 10**9
        push_influx_generic(measure, tags, int(ts), fields)


if __name__ == "__main__":
    main()
