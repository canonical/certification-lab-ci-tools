from abc import ABC, abstractmethod
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple
import yaml

from toolbox.entities.connections import PlugDict, SlotDict, SnapConnection


class PredicateCheckResult(NamedTuple):
    """
    Contains the result of a connection predicate test, along with a possible
    message explaining the result.
    """

    result: bool
    message: str | None = None

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

    def __init__(self, snaps: list[str]):
        self.snaps = set(snaps)

    def check(self, plug: PlugDict, slot: SlotDict) -> PredicateCheckResult:
        return PredicateCheckResult(plug["snap"] in self.snaps)


class Blacklist(Predicate):
    """Only select connections that haven't been blacklisted."""

    def __init__(self, blacklist: list[SnapConnection]):
        self.blacklist = blacklist

    @classmethod
    def from_dict(cls, blacklist_data: dict) -> "Blacklist":
        return cls(
            [
                SnapConnection(
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
            else f"Connection '{SnapConnection.from_dicts(plug, slot)}' is blacklisted"
        )
        return PredicateCheckResult(result, message)


class SnapConnector:
    def __init__(self, predicates: list[Predicate] | None = None):
        # specify the predicate functions that will be used by default
        # to select or filter out possible connections between plus and slots
        self.predicates = [MatchAttributes, DifferentSnaps]
        # additional user-provided filtering predicates
        if predicates:
            self.predicates.extend(predicates)

    def process(self, snap_connection_data) -> tuple[set[SnapConnection], list[str]]:
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
        for plug in snap_connection_data["plugs"]:
            if "connections" not in plug:
                interface = plug["interface"]
                interface_plugs[interface].append(plug)

        # iterate over all slots and check for plugs that satisfy all the
        # filtering predicates to form the set of possible connections
        connections = set()
        aggregate_messages = []
        for slot in snap_connection_data["slots"]:
            if (interface := slot["interface"]) in interface_plugs:
                for plug in interface_plugs[interface]:
                    results, messages = zip(
                        *(predicate.check(plug, slot) for predicate in self.predicates)
                    )
                    if all(results):
                        connections.add(SnapConnection.from_dicts(plug, slot))
                    aggregate_messages.extend(filter(bool, messages))
        return connections, messages
