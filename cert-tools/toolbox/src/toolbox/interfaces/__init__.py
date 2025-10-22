from abc import ABC
from typing import Iterable, Type


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
