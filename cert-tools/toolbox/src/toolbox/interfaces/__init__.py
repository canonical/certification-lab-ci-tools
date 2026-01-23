"""Interfaces are attached to devices, endowing them with specific capabilities (like rebooting or managing snaps)."""

from abc import ABC
from typing import Iterable, Type


class DeviceInterfaceError(AttributeError):
    pass


class DeviceInterface(ABC):
    """Base class for device capabilities that can be attached to devices."""

    requires: Iterable[Type["DeviceInterface"]]

    def __init_subclass__(
        cls, *, requires: Iterable[Type["DeviceInterface"]] | None = None
    ):
        """Register interface dependencies declared via the requires parameter."""
        cls.requires = tuple(requires or ())

    def __init__(self):
        self._device = None

    @property
    def device(self) -> "Device":  # noqa: F821
        """Return the device this interface is attached to."""
        if self._device is None:
            raise DeviceInterfaceError(
                f"'{type(self).__name__}' is not attached to a device"
            )
        return self._device

    def attach_to(self, device: "Device"):  # noqa: F821
        """Attach this interface to a device, allowing commands to be executed via self.device.run()."""
        self._device = device
