"""Tests for the toolbox.devices.registry module."""

import pytest

from toolbox.interfaces import DeviceInterface, DeviceInterfaceError
from toolbox.devices.registry import DeviceInterfaceRegistry


# Test interface classes
class InterfaceA(DeviceInterface):
    """Test interface with no dependencies."""

    pass


class InterfaceB(DeviceInterface):
    """Test interface with no dependencies."""

    pass


class InterfaceC(DeviceInterface, requires=(InterfaceA,)):
    """Test interface that requires InterfaceA."""

    pass


class InterfaceD(DeviceInterface, requires=(InterfaceA, InterfaceB)):
    """Test interface that requires both InterfaceA and InterfaceB."""

    pass


class TestDeviceInterfaceRegistry:
    """Tests for the DeviceInterfaceRegistry."""

    def test_register_single_interface(self):
        """Test registering a single interface."""
        interface_a = InterfaceA()
        registry = DeviceInterfaceRegistry([interface_a])

        retrieved = registry[InterfaceA]
        assert retrieved is interface_a

    def test_register_multiple_interfaces(self):
        """Test registering multiple interfaces."""
        interface_a = InterfaceA()
        interface_b = InterfaceB()
        registry = DeviceInterfaceRegistry([interface_a, interface_b])

        assert registry[InterfaceA] is interface_a
        assert registry[InterfaceB] is interface_b

    def test_duplicate_interface_raises_error(self):
        """Test that registering duplicate interfaces raises an error."""
        interface_a1 = InterfaceA()
        interface_a2 = InterfaceA()

        with pytest.raises(
            DeviceInterfaceError, match="Duplicate 'InterfaceA' interface"
        ):
            DeviceInterfaceRegistry([interface_a1, interface_a2])

    def test_retrieve_nonexistent_interface_raises_error(self):
        """Test that retrieving a non-registered interface raises an error."""
        registry = DeviceInterfaceRegistry([])

        with pytest.raises(
            DeviceInterfaceError, match="No InterfaceA interface registered"
        ):
            registry[InterfaceA]

    def test_missing_required_interface_raises_error(self):
        """Test that missing required interfaces raises an error during initialization."""
        interface_c = InterfaceC()

        with pytest.raises(
            DeviceInterfaceError, match="Missing required interfaces: InterfaceA"
        ):
            DeviceInterfaceRegistry([interface_c])

    def test_multiple_missing_required_interfaces_raises_error(self):
        """Test that multiple missing required interfaces are reported."""
        interface_d = InterfaceD()

        with pytest.raises(
            DeviceInterfaceError,
            match="Missing required interfaces: InterfaceA, InterfaceB",
        ):
            DeviceInterfaceRegistry([interface_d])

    def test_satisfied_dependencies(self):
        """Test that registry accepts interfaces when all dependencies are satisfied."""
        interface_a = InterfaceA()
        interface_c = InterfaceC()

        # should not raise
        registry = DeviceInterfaceRegistry([interface_a, interface_c])

        assert registry[InterfaceA] is interface_a
        assert registry[InterfaceC] is interface_c

    def test_satisfied_multiple_dependencies(self):
        """Test that registry accepts interfaces with multiple satisfied dependencies."""
        interface_a = InterfaceA()
        interface_b = InterfaceB()
        interface_d = InterfaceD()

        # should not raise
        registry = DeviceInterfaceRegistry([interface_a, interface_b, interface_d])

        assert registry[InterfaceA] is interface_a
        assert registry[InterfaceB] is interface_b
        assert registry[InterfaceD] is interface_d

    def test_iterate_over_interfaces(self):
        """Test that the registry can be iterated over."""
        interface_a = InterfaceA()
        interface_b = InterfaceB()
        registry = DeviceInterfaceRegistry([interface_a, interface_b])

        interfaces = list(registry)
        assert len(interfaces) == 2
        assert interface_a in interfaces
        assert interface_b in interfaces

    def test_empty_registry(self):
        """Test that an empty registry works correctly."""
        registry = DeviceInterfaceRegistry([])

        interfaces = list(registry)
        assert len(interfaces) == 0

    def test_interface_registration_order_independence(self):
        """Test that interfaces can be registered in any order."""
        interface_a = InterfaceA()
        interface_c = InterfaceC()

        # register dependent before dependency - should still work
        registry = DeviceInterfaceRegistry([interface_c, interface_a])

        assert registry[InterfaceA] is interface_a
        assert registry[InterfaceC] is interface_c

    def test_partial_dependency_satisfaction_raises_error(self):
        """Test that only partially satisfied dependencies still raise an error."""
        interface_a = InterfaceA()
        interface_d = InterfaceD()

        # InterfaceD requires both InterfaceA and InterfaceB, but only InterfaceA is provided
        with pytest.raises(
            DeviceInterfaceError, match="Missing required interfaces: InterfaceB"
        ):
            DeviceInterfaceRegistry([interface_a, interface_d])
