import re
from typing import NamedTuple

# dicts that describe snap plugs and slots
# (they follow the schema of the snapd API `connections` endpoint)
# ref: https://snapcraft.io/docs/snapd-api#heading--connections
#
# Here's one way of retrieving this data from the endpoint:
# printf 'GET /v2/connections?select=all HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n' | \
# nc -U /run/snapd.socket | \
# grep -o '{.*}'
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
PlugDict = dict
SlotDict = dict


class SnapConnection(NamedTuple):
    plug_snap: str
    plug_name: str
    slot_snap: str
    slot_name: str

    @classmethod
    def from_dicts(cls, plug: PlugDict, slot: SlotDict) -> "SnapConnection":
        return cls(
            plug_snap=plug["snap"],
            plug_name=plug["plug"],
            slot_snap=slot["snap"],
            slot_name=slot["slot"],
        )

    @classmethod
    def from_string(cls, string: str) -> "SnapConnection":
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
