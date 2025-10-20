from dataclasses import dataclass, astuple
from enum import Enum
import re


class Risk(str, Enum):
    STABLE = "stable"
    CANDIDATE = "candidate"
    BETA = "beta"
    EDGE = "edge"

    @classmethod
    def validate(cls, value: str) -> bool:
        try:
            Risk(value.lower())
            return True
        except ValueError:
            return False


@dataclass
class Channel:
    track: str | None = None
    risk: str | None = None
    branch: str | None = None

    def __post_init__(self):
        if self.track is None and self.risk is None:
            raise ValueError("At least one of track or risk must be set")
        if self.risk is not None and not Risk.validate(self.risk):
            raise ValueError(f"'{self.risk}' is not a valid risk")

    @classmethod
    def from_string(cls, channel: str) -> "Channel":
        # template for matching snap channels in the form track/risk/branch
        # (only one of track or risk is required)
        channel_template = r"^(?:([\w.-]+)(?:/([\w-]+)(?:/([\w-]+))?)?)?$"
        match = re.match(channel_template, channel)
        if not match:
            raise ValueError(f"Cannot parse '{channel}' as a snap channel")
        components = tuple(component for component in match.groups() if component)
        # check if a shift of the components is required (in case a track is not specified)
        if 0 < len(components) < 3 and Risk.validate(components[0]):
            # the first of the components matches a risk
            try:
                # if the second component also matches a risk then the first one is a track
                track_specified = Risk.validate(components[1])
            except IndexError:
                # if there is no second component then the first one is a risk
                track_specified = False
            if not track_specified:
                # the first match is the risk: shift the components
                components = (None, *components)
        return cls(*components)

    def __str__(self):
        return "/".join(component for component in astuple(self) if component)
