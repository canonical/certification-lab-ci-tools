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
import datetime
import re
import requests
import time
import os

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
    fields["time-to-candidate"] = age
    measure = "time-to-candidate"
    push_influx_generic(measure, tags, whenmoved, fields)


def main():
    print("init influx")
    init_influx()
    print("influx initialized")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--key", help="Trello API key", **environ_or_required("TRELLO_API_KEY")
    )
    parser.add_argument(
        "--token", help="Trello OAuth token", **environ_or_required("TRELLO_TOKEN")
    )
    parser.add_argument(
        "--board", help="Trello board identifier", **environ_or_required("TRELLO_BOARD")
    )
    args = parser.parse_args()
    client = TrelloClient(api_key=args.key, token=args.token)
    board = client.get_board(args.board)
    all_cards = board.get_cards(card_filter="open")
    print("got cards")
    for c in all_cards:
        print(c.name)
        m = re.match(
            r"(?P<snap>.*?)(?:\s+\-\s+)(?P<version>.*?)(?:\s+\-\s+)"
            r"\((?P<revision>.*?)\)(?:\s+\-\s+\[(?P<track>.*?)\])?",
            c.name,
        )
        for move in c.list_movements():
            if (
                move["destination"]["name"] == "Candidate"
                and move["source"]["name"] == "Beta"
            ):
                notz = move["datetime"].replace(tzinfo=None)
                diff = notz - c.card_created_date
                diff.total_seconds()
                print(diff.total_seconds)
                ns = notz.timestamp() * 10**9
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
