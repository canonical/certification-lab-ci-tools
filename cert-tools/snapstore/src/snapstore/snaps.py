import re
from dataclasses import dataclass, astuple


@dataclass(frozen=True)
class SnapChannel:
    track: str | None = None
    risk: str | None = None
    branch: str | None = None

    def __post_init__(self):
        if self.track is None and self.risk is None:
            raise ValueError("At least one of track or risk must be set")

    @classmethod
    def from_string(cls, string):
        # template for matching snap channels in the form track/risk/branch
        # (only one of the components is required)
        channel_template = r"^(?:([\w.-]+)(?:/([\w-]+)(?:/([\w-]+))?)?)?$"
        match = re.match(channel_template, string)
        if not match:
            raise ValueError(f"Cannot parse '{string}' as a snap channel")
        components = tuple(component for component in match.groups() if component)
        if components and components[0] in {"stable", "candidate", "beta", "edge"}:
            components = (None, *components)
        return cls(*components)

    def __str__(self):
        return "/".join(component for component in astuple(self) if component)


@dataclass(frozen=True)
class SnapSpecifier:
    name: str
    channel: SnapChannel

    @classmethod
    def from_string(cls, string):
        # template for matching snap specifiers in the form snap=channel
        # (only one of the components is required)
        specifier_template = r"^([\w-]+)=(.+)$"
        match = re.match(specifier_template, string)
        if not match:
            raise ValueError(f"Cannot parse '{string}' as a snap specifier")
        name, channel = match.groups()
        channel = SnapChannel.from_string(channel)
        return cls(name=name, channel=channel)

    def __str__(self):
        return f"{self.name}={self.channel}"
