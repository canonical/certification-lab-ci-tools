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

import argparse
import os
import re

from dateutil import parser
from influxdb import InfluxDBClient
from trello import TrelloClient

INFLUX_HOST = "10.50.124.12"


def environ_or_required(key):
    """Mapping for argparse to supply required or default from $ENV."""
    if os.environ.get(key):
        return {"default": os.environ.get(key)}
    else:
        return {"required": True}


def init_influx():
    """Init influxdb with policy"""
    dbname = "candidatesnaps"
    client = InfluxDBClient(
        INFLUX_HOST, 8086, "ce", os.environ.get("INFLUX_PASS"), dbname
    )
    dbs = client.get_list_database()
    if {"name": dbname} not in dbs:
        client.create_database(dbname)
        client.create_retention_policy("default_policy", "350w", 1, default=True)


def push_influx_generic(measurement, tags, time, fields):
    """Generic influx measurement pusher"""
    dbname = "candidatesnaps"
    client = InfluxDBClient(
        INFLUX_HOST, 8086, "ce", os.environ.get("INFLUX_PASS"), dbname
    )
    body = [{"measurement": measurement, "tags": tags, "time": time, "fields": fields}]
    client.write_points(body)
    print("measurement: %s at: %s pushed to influx", measurement, str(time))


def influx_push(age, snap, whenmoved, revno, version):
    tags = dict()
    fields = dict()
    tags["snap"] = snap
    tags["revision"] = revno
    tags["version"] = version
    fields["time-to-plusone"] = age
    measure = "time-to-plusone"
    print(version)
    push_influx_generic(measure, tags, whenmoved, fields)


def main():
    print("Initialize influx")
    init_influx()
    print("Influx initialized")
    aparser = argparse.ArgumentParser()
    aparser.add_argument(
        "--key", help="Trello API key", **environ_or_required("TRELLO_API_KEY")
    )
    aparser.add_argument(
        "--token", help="Trello OAuth token", **environ_or_required("TRELLO_TOKEN")
    )
    aparser.add_argument(
        "--board", help="Trello board identifier", **environ_or_required("TRELLO_BOARD")
    )
    args = aparser.parse_args()
    client = TrelloClient(api_key=args.key, token=args.token)
    board = client.get_board(args.board)
    all_cards = board.get_cards(card_filter="open")
    for c in all_cards:
        m = re.match(
            r"(?P<snap>.*?)(?:\s+\-\s+)(?P<version>.*?)(?:\s+\-\s+)"
            r"\((?P<revision>.*?)\)(?:\s+\-\s+\[(?P<track>.*?)\])?",
            c.name,
        )
        acts = c.attriExp("updateCheckItemStateOnCard")
        for act in acts:
            if (
                act["type"] == "updateCheckItemStateOnCard"
                and act["data"]["checklist"]["name"] == "Sign-Off"
                and act["data"]["checkItem"]["name"] == "Ready for Candidate"
                and act["data"]["checkItem"]["state"] == "complete"
            ):
                when = parser.parse(act["date"]).replace(tzinfo=None)
                diff = when - c.card_created_date
                print(diff.total_seconds())
                ns = when.timestamp() * 10**9
                print(ns)
                try:
                    influx_push(
                        diff.total_seconds(),
                        c.name.split(" ")[0],
                        int(ns),
                        m.group("revision"),
                        m.group("version"),
                    )
                except AttributeError:
                    print("cards with no revision aren't helpful")


if __name__ == "__main__":
    main()
