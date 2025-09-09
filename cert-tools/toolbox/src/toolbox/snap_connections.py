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

from abc import ABC, abstractmethod
from argparse import ArgumentParser
from collections import defaultdict
import json
import logging
from pathlib import Path
import re
import sys
from typing import Dict, List, NamedTuple, Optional, Set
import yaml

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

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


class PredicateCheckResult(NamedTuple):
    """
    Contains the result of a connection predicate test, along with a possible
    message explaining the result.
    """

    result: bool
    message: Optional[str] = None

    def __bool__(self) -> bool:
        return self.result


class Predicate(ABC):
    @abstractmethod
    def check(self, plug: PlugDict, slot: SlotDict) -> PredicateCheckResult:
        """
        Return a PredicateCheckResult which is True if the plug and slot
        should be connected or False otherwise.
        """
        raise NotImplementedError


class MatchAttributes(Predicate):
    @staticmethod
    def check(plug: PlugDict, slot: SlotDict) -> PredicateCheckResult:
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
            return PredicateCheckResult(True)
        common_attributes = set(plug_attributes.keys()) & set(slot_attributes.keys())
        return PredicateCheckResult(
            all(
                plug_attributes[attribute] == slot_attributes[attribute]
                for attribute in common_attributes
            )
        )


class DifferentSnaps(Predicate):
    """Only select connections between different snaps."""

    @staticmethod
    def check(plug: PlugDict, slot: SlotDict) -> PredicateCheckResult:
        return PredicateCheckResult(plug["snap"] != slot["snap"])


class SelectSnaps(Predicate):
    """Only select connections plugging specific snaps."""

    def __init__(self, snaps: List[str]):
        self.snaps = set(snaps)

    def check(self, plug: PlugDict, slot: SlotDict) -> PredicateCheckResult:
        return PredicateCheckResult(plug["snap"] in self.snaps)


class Blacklist(Predicate):
    """Only select connections that haven't been blacklisted."""

    def __init__(self, blacklist: List[Connection]):
        self.blacklist = blacklist

    @classmethod
    def from_dict(cls, blacklist_data: dict) -> "Blacklist":
        return cls(
            [
                Connection(
                    plug_snap=entry.get("plug_snap"),
                    plug_name=entry.get("plug_name"),
                    slot_snap=entry.get("slot_snap"),
                    slot_name=entry.get("slot_name"),
                )
                for item in blacklist_data["items"]
                for entry in item["match"]
            ]
        )

    @classmethod
    def from_file(cls, path: Path) -> "Blacklist":
        with open(path) as file:
            blacklist_data = yaml.safe_load(file)
            return cls.from_dict(blacklist_data)

    def check(self, plug: PlugDict, slot: SlotDict) -> PredicateCheckResult:
        result = not any(
            (entry.plug_snap is None or entry.plug_snap == plug["snap"])
            and (entry.plug_name is None or entry.plug_name == plug["plug"])
            and (entry.slot_snap is None or entry.slot_snap == slot["snap"])
            and (entry.slot_name is None or entry.slot_name == slot["slot"])
            for entry in self.blacklist
        )
        message = (
            None
            if result
            else f"Connection '{Connection.from_dicts(plug, slot)}' is blacklisted"
        )
        return PredicateCheckResult(result, message)


class Connector:
    def __init__(self, predicates: Optional[List[Predicate]] = None):
        # specify the predicate functions that will be used by default
        # to select or filter out possible connections between plus and slots
        self.predicates = [MatchAttributes, DifferentSnaps]
        # additional user-provided filtering predicates
        if predicates:
            self.predicates.extend(predicates)

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
        connections = set()
        for slot in snap_connection_data["result"]["slots"]:
            if (interface := slot["interface"]) in interface_plugs:
                for plug in interface_plugs[interface]:
                    results, messages = zip(
                        *(predicate.check(plug, slot) for predicate in self.predicates)
                    )
                    if all(results):
                        connections.add(Connection.from_dicts(plug, slot))
                    for message in filter(bool, messages):
                            logger.info(message)
        return connections


def main(args: Optional[List[str]] = None):
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
    parser.add_argument(
        "--blacklist", type=Path, help="Path to the connections blacklist"
    )
    parser.add_argument(
        "--output", type=Path, help="Output file path (default: stdout)"
    )
    args = parser.parse_args(args)

    # parse standard input as JSON
    snap_connection_data = json.load(sys.stdin)

    # determine additional connection predicates from arguments
    predicates = [SelectSnaps(args.snaps)]
    if args.blacklist:
        predicates.append(Blacklist.from_file(args.blacklist))

    connector = Connector(predicates)
    snap_connections = connector.process(snap_connection_data)
    output = (
        str(connection) for connection in sorted(snap_connections) + (args.force or [])
    )

    if args.output:
        with open(args.output, "w") as f:
            f.write("\n".join(output) + "\n")
    else:
        for line in output:
            print(line)


if __name__ == "__main__":
    main()
