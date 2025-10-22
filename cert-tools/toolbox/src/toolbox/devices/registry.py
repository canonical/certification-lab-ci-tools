"""Registry for managing device interfaces and their dependencies."""

from typing import Iterable, Iterator, Type, TypeVar

from toolbox.interfaces import DeviceInterface, DeviceInterfaceError


T = TypeVar("T", bound=DeviceInterface)


class DeviceInterfaceRegistry:
    """Stores device interfaces by class name and validates their dependencies.

    The interface registry is normally part of a Device.

    The fact that the interfaces in the registry are indexed by interface class
    provides the mechanism that allows access to a device's interfaces like, e.g.
    `device.interfaces[RebootInterface]`.

    Dependency validation ensures that all the interfaces attached to a
    device also have any required interfaces also attached.
    """

    def __init__(self, interfaces: Iterable[DeviceInterface] | None = None):
        self.registry = {}
        for interface in interfaces:
            self._register(interface)
        self._check_requirements()

    def __getitem__(self, interface_cls: Type[T]) -> T:
        """Retrieve an interface by its class type."""
        identifier = interface_cls.__name__
        try:
            return self.registry[identifier]
        except KeyError as error:
            raise DeviceInterfaceError(
                f"No {identifier} interface registered"
            ) from error

    def __iter__(self) -> Iterator[DeviceInterface]:
        """Iterate over all registered interfaces."""
        yield from self.registry.values()

    def _register(self, interface: DeviceInterface):
        """Register an interface, raising an error if it's already registered."""
        identifier = type(interface).__name__
        if identifier in self.registry:
            raise DeviceInterfaceError(f"Duplicate '{identifier}' interface")
        self.registry[identifier] = interface

    def _check_requirements(self):
        """Validate that all interface dependencies are satisfied."""
        requirements = set(
            requirement.__name__
            for interface in self
            for requirement in interface.requires
        )
        registered = set(identifier for identifier in self.registry)
        missing = requirements - registered
        if missing:
            missing_message = ", ".join(sorted(missing))
            raise DeviceInterfaceError(
                f"Missing required interfaces: {missing_message}"
            )
