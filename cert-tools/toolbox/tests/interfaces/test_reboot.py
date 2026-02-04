"""Tests for the toolbox.interfaces.reboot module."""

from invoke import Result

from toolbox.interfaces.reboot import RebootInterface
from tests.devices.trivial import TrivialDevice


class TestReboot:
    """Tests for RebootInterface."""

    def test_reboot_required_returns_true(self, mocker):
        """Test is_reboot_required returns True when file exists."""
        device = TrivialDevice(interfaces=[RebootInterface()])
        device.run = mocker.Mock(return_value=Result(stdout="", exited=0))

        result = device.interfaces[RebootInterface].is_reboot_required()

        assert result is True
        device.run.assert_called_once_with(["test", "-f", "/run/reboot-required"])

    def test_reboot_not_required_returns_false(self, mocker):
        """Test is_reboot_required returns False when file doesn't exist."""
        device = TrivialDevice(interfaces=[RebootInterface()])
        device.run = mocker.Mock(return_value=Result(stdout="", exited=1))

        result = device.interfaces[RebootInterface].is_reboot_required()

        assert result is False
        device.run.assert_called_once_with(["test", "-f", "/run/reboot-required"])

    def test_reboot_successful(self, mocker):
        """Test reboot returns True when successful."""
        device = TrivialDevice(interfaces=[RebootInterface()])
        device.run = mocker.Mock(return_value=Result(stdout="", exited=0))

        result = device.interfaces[RebootInterface].reboot()

        assert result is True
        device.run.assert_called_once_with(["sudo", "reboot"])

    def test_reboot_fails(self, mocker):
        """Test reboot returns False when it fails."""
        device = TrivialDevice(interfaces=[RebootInterface()])
        device.run = mocker.Mock(return_value=Result(stdout="", exited=1))

        result = device.interfaces[RebootInterface].reboot()

        assert result is False
        device.run.assert_called_once_with(["sudo", "reboot"])
