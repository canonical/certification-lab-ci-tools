from typing import NamedTuple

from toolbox.entities.channels import Channel


class SnapSpecifier(NamedTuple):
    name: str
    channel: Channel

    @classmethod
    def from_string(cls, specifier: str) -> "SnapSpecifier":
        try:
            name, channel = specifier.split("=")
        except ValueError as error:
            raise ValueError(
                f"Cannot parse '{specifier}' as a snap specifier"
            ) from error
        try:
            channel = Channel.from_string(channel)
        except ValueError as error:
            raise ValueError(
                f"Cannot parse '{specifier}' as a snap specifier"
            ) from error
        return cls(name=name, channel=channel)

    def __str__(self) -> str:
        return f"{self.name}={self.channel}"
