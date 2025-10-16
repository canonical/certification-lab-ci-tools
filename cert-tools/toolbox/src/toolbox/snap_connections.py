#!/usr/bin/env python3
"""
Read the output of the `connections` endpoint of the snapd API
from standard input and write a list of possible plug-to-slot
connections to standard output.

Ref: https://snapcraft.io/docs/snapd-api#heading--connections

As an aid, here's one way of retrieving this data from the endpoint:
```
printf 'GET /v2/connections?select=all HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n' | \
nc -U /run/snapd.socket | \
grep -o '{.*}'
```
"""

from argparse import ArgumentParser
from collections import defaultdict
import json
import re
import sys
from typing import Callable, Dict, List, NamedTuple, Set


# dicts that describe snap plugs and slots
# (they follow the schema of the snapd API `connections` endpoint)
#
# example of a plug dict:
# ```
# {
#   "snap": "checkbox-mir",
#   "plug": "graphics-core22",
#   "interface": "content",
#   "attrs": {
#     "content": "graphics-core22",
#     "default-provider": "mesa-core22",
#   },
#   "connections": [
#     {
#       "snap": "mesa-core22",
#       "slot": "graphics-core22"
#     }
#   ]
# }
# ```
#
# example of a slot dict:
# ```
# {
#     "snap": "mesa-core22",
#     "slot": "graphics-core22",
#     "interface": "content",
#     "attrs": {
#         "content": "graphics-core22",
#     },
#     "connections": [
#         {
#             "snap": "checkbox-mir",
#             "plug": "graphics-core22"
#         }
#     ]
# }
# ```
PlugDict = Dict
SlotDict = Dict


class Connection(NamedTuple):
    plug_snap: str
    plug_name: str
    slot_snap: str
    slot_name: str

    @classmethod
    def from_dicts(cls, plug: PlugDict, slot: SlotDict) -> "Connection":
        return cls(
            plug_snap=plug["snap"],
            plug_name=plug["plug"],
            slot_snap=slot["snap"],
            slot_name=slot["slot"],
        )

    @classmethod
    def from_string(cls, string: str) -> "Connection":
        match = re.match(
            r"^(?P<plug_snap>[\w-]+):(?P<plug_name>[\w-]+)"
            r"/(?P<slot_snap>[\w-]*):(?P<slot_name>[\w-]+)$",
            string,
        )
        if not match:
            raise ValueError(f"'{string}' cannot be converted to a snap connection")
        return cls(
            plug_snap=match.group("plug_snap"),
            plug_name=match.group("plug_name"),
            slot_snap=match.group("slot_snap") or "snapd",
            slot_name=match.group("slot_name"),
        )

    def __str__(self):
        return f"{self.plug_snap}:{self.plug_name}/{self.slot_snap}:{self.slot_name}"


# any callable that processes a plug-to-dict connection and accepts/rejects it
ConnectionPredicate = Callable[[PlugDict, SlotDict], bool]


class Connector:
    def __init__(self, predicates: List[ConnectionPredicate] | None = None):
        # specify the predicate functions that will be used to select or
        # filter out possible connections between plus and slots
        self.predicates = [
            # select connections where the interface attributes match
            self.matching_attributes,
            # select connections only on different snaps
            lambda plug, slot: plug["snap"] != slot["snap"],
        ]
        # additional user-provided filtering predicates
        if predicates:
            self.predicates.extend(predicates)

    @staticmethod
    def matching_attributes(plug: PlugDict, slot: SlotDict) -> bool:
        """
        Return True if the (common) attributes of a plug and slot match, or
        if there are no common attributes and return False otherwise.

        This is relevant in e.g. `content` interfaces where a connection
        should be made only if the corresponding attributes match.

        For example:
        ```
        plug = {
            "interface": "content",
            "attrs": {"content": "graphics-core22", "extra": "value"}
        }
        slot = {
            "interface": "content",
            "attrs": {"content": "graphics-core22", "other": "data"}
        }
        assert Connector.matching_attributes(plug, slot)
        ```
        """
        assert plug["interface"] == slot["interface"]
        try:
            plug_attributes = plug["attrs"]
            slot_attributes = slot["attrs"]
        except KeyError:
            return True
        common_attributes = set(plug_attributes.keys()) & set(slot_attributes.keys())
        return all(
            plug_attributes[attribute] == slot_attributes[attribute]
            for attribute in common_attributes
        )

    def process(self, snap_connection_data) -> Set[Connection]:
        """
        Process the output of the `connections` endpoint of the snapd API
        and return a set of possible connections (`Connection` objects).

        Note: the output will not include possible connections for plugs
        that are already connected but it will connect a plug to multiple
        slots if that plug is originally unconnected.
        """
        # iterate over all *unconnected* plugs and create a map that
        # associates each interface to a list of plugs for that interface
        interface_plugs = defaultdict(list)
        for plug in snap_connection_data["result"]["plugs"]:
            if "connections" not in plug:
                interface = plug["interface"]
                interface_plugs[interface].append(plug)

        # iterate over all slots and check for plugs that satisfy all the
        # filtering predicates to form the set of possible connections
        return {
            Connection.from_dicts(plug, slot)
            for slot in snap_connection_data["result"]["slots"]
            if (interface := slot["interface"]) in interface_plugs
            for plug in interface_plugs[interface]
            if all(predicate(plug, slot) for predicate in self.predicates)
        }


def main(args: List[str] | None = None):
    parser = ArgumentParser()
    parser.add_argument(
        "snaps",
        nargs="+",
        type=str,
        help="Connect plugs for these snaps to slots on matching interfaces",
    )
    parser.add_argument(
        "--force",
        nargs="+",
        type=Connection.from_string,
        help="Force additional connections",
    )
    args = parser.parse_args(args)

    # parse standard input as JSON
    snap_connection_data = json.load(sys.stdin)

    # create a predicate function for the provided snaps
    def snap_select(plug: PlugDict, _) -> bool:
        return plug["snap"] in set(args.snaps)

    predicates = [snap_select]
    connector = Connector(predicates)

    snap_connections = connector.process(snap_connection_data)
    for connection in sorted(snap_connections) + (args.force or []):
        print(connection)


if __name__ == "__main__":
    main()
