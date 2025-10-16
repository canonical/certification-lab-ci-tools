from typing import Iterable, Iterator, Type, TypeVar

from toolbox.interfaces import DeviceInterface, DeviceInterfaceError


T = TypeVar("T", bound=DeviceInterface)


class DeviceInterfaceRegistry:
    def __init__(self, interfaces: Iterable[DeviceInterface] | None = None):
        self.registry = {}
        for interface in interfaces:
            self._register(interface)
        self._check_requirements()

    def __getitem__(self, interface_cls: Type[T]) -> T:
        identifier = interface_cls.__name__
        try:
            return self.registry[identifier]
        except KeyError as error:
            raise DeviceInterfaceError(
                f"No {identifier} interface registered"
            ) from error

    def __iter__(self) -> Iterator[DeviceInterface]:
        yield from self.registry.values()

    def _register(self, interface: DeviceInterface):
        identifier = type(interface).__name__
        if identifier in self.registry:
            raise DeviceInterfaceError(f"Duplicate '{identifier}' interface")
        self.registry[identifier] = interface

    def _check_requirements(self):
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
