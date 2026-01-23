"""Tests for Device base class and helper methods."""

from toolbox.devices import Device
from toolbox.interfaces import DeviceInterface


# Test interfaces
class InterfaceA(DeviceInterface):
    """Simple test interface."""

    pass


class InterfaceB(DeviceInterface):
    """Another simple test interface."""

    pass


class TestDeviceProcess:
    """Tests for Device._process() static method."""

    def test_process_string_command(self):
        """Test that string commands are returned as-is."""
        command = "ls -la /home"
        result = Device._process(command)
        assert result == "ls -la /home"

    def test_process_list_command(self):
        """Test that list commands are joined with shlex."""
        command = ["ls", "-la", "/home"]
        result = Device._process(command)
        assert result == "ls -la /home"

    def test_process_list_with_spaces(self):
        """Test that list commands with spaces are properly quoted."""
        command = ["echo", "hello world", "test"]
        result = Device._process(command)
        assert result == "echo 'hello world' test"

    def test_process_list_with_special_chars(self):
        """Test that special characters are properly escaped."""
        command = ["echo", "$HOME"]
        result = Device._process(command)
        assert result == "echo '$HOME'"
