"""Tests for Device initialization and interface attachment."""

import pytest

from toolbox.interfaces import DeviceInterface, DeviceInterfaceError

from tests.devices.trivial import TrivialDevice


# Test interfaces
class InterfaceA(DeviceInterface):
    """Simple test interface."""

    pass


class InterfaceB(DeviceInterface):
    """Another simple test interface."""

    pass


class InterfaceC(DeviceInterface, requires=(InterfaceA,)):
    """Test interface that requires InterfaceA."""

    pass


class TestDeviceInitialization:
    """Tests for device initialization."""

    def test_device_with_no_interfaces(self):
        """Test creating a device with no interfaces."""
        device = TrivialDevice()
        assert device is not None
        assert list(device.interfaces) == []
        assert str(device) == "TrivialDevice('test-host')"

    def test_device_with_single_interface(self):
        """Test creating a device with a single interface."""
        interface = InterfaceA()
        device = TrivialDevice(interfaces=[interface])

        assert device.interfaces[InterfaceA] is interface
        assert interface.device is device

    def test_device_with_multiple_interfaces(self):
        """Test creating a device with multiple interfaces."""
        interface_a = InterfaceA()
        interface_b = InterfaceB()
        device = TrivialDevice(interfaces=[interface_a, interface_b])

        assert device.interfaces[InterfaceA] is interface_a
        assert device.interfaces[InterfaceB] is interface_b
        assert interface_a.device is device
        assert interface_b.device is device

    def test_device_with_dependent_interfaces(self):
        """Test creating a device with interfaces that have dependencies."""
        interface_a = InterfaceA()
        interface_c = InterfaceC()
        device = TrivialDevice(interfaces=[interface_a, interface_c])

        assert device.interfaces[InterfaceA] is interface_a
        assert device.interfaces[InterfaceC] is interface_c

    def test_device_with_missing_dependencies_raises_error(self):
        """Test that missing interface dependencies raise an error."""
        interface_c = InterfaceC()

        with pytest.raises(
            DeviceInterfaceError, match="Missing required interfaces: InterfaceA"
        ):
            TrivialDevice(interfaces=[interface_c])

    def test_interface_requires_device_attachment(self):
        """Test that accessing device on unattached interface raises an error."""
        interface = InterfaceA()

        with pytest.raises(
            DeviceInterfaceError, match="'InterfaceA' is not attached to a device"
        ):
            interface.device
