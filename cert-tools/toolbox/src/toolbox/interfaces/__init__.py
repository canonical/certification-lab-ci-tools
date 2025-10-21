from abc import ABC
from typing import Iterable, NamedTuple, Type


class DeviceInterfaceError(AttributeError):
    pass


class DeviceInterface(ABC):
    requires: Iterable[Type["DeviceInterface"]]

    def __init_subclass__(
        cls, *, requires: Iterable[Type["DeviceInterface"]] | None = None
    ):
        cls.requires = tuple(requires or ())

    def __init__(self):
        self._device = None

    @property
    def device(self) -> "Device":  # noqa: F821
        if self._device is None:
            raise DeviceInterfaceError(
                f"'{type(self).__name__}' is not attached to a device"
            )
        return self._device

    def attach_to(self, device: "Device"):  # noqa: F821
        self._device = device


class BooleanResult(NamedTuple):
    ok: bool
    message: str | None = None

    def __bool__(self) -> bool:
        return self.ok

    def __str__(self) -> str:
        return f"[{self.ok}]" + f" {self.message}" if self.message else ""
