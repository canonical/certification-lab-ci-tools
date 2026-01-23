"""Tests for CheckboxInstaller base class."""

import pytest
from invoke import Result

from toolbox.checkbox.installers import CheckboxInstaller, CheckboxInstallerError
from tests.devices.trivial import TrivialDevice


class ConcreteInstaller(CheckboxInstaller):
    """Concrete implementation of CheckboxInstaller for testing."""

    @property
    def checkbox_cli(self):
        """Return the command to invoke the Checkbox CLI."""
        return "checkbox-cli"

    def install_on_device(self, *args, **kwargs):
        """Mock installation on device."""
        pass


class TestCheckboxInstaller:
    """Tests for CheckboxInstaller."""

    def test_check_service_active(self, mocker):
        """Test check_service when service is active."""
        device = TrivialDevice()
        device.run = mocker.Mock(return_value=Result(stdout="active\n", exited=0))

        installer = ConcreteInstaller(device, TrivialDevice())
        installer.check_service()

        device.run.assert_called_once_with(
            ["systemctl", "is-active", "*checkbox*.service"]
        )

    def test_check_service_inactive(self, mocker):
        """Test check_service raises error when service is not active."""
        device = TrivialDevice()
        device.run = mocker.Mock(return_value=Result(stdout="inactive\n", exited=1))

        installer = ConcreteInstaller(device, TrivialDevice())

        with pytest.raises(
            CheckboxInstallerError, match="Checkbox service is not active"
        ):
            installer.check_service()

    def test_check_service_no_result(self, mocker):
        """Test check_service raises error when command fails."""
        device = TrivialDevice()
        device.run = mocker.Mock(return_value=None)

        installer = ConcreteInstaller(device, TrivialDevice())

        with pytest.raises(
            CheckboxInstallerError, match="Checkbox service is not active"
        ):
            installer.check_service()

    def test_get_version_success(self, mocker):
        """Test get_version returns version string."""
        device = TrivialDevice()
        device.run = mocker.Mock(return_value=Result(stdout="4.0.0.dev42\n", exited=0))

        installer = ConcreteInstaller(device, TrivialDevice())
        version = installer.get_version()

        assert version == "4.0.0.dev42"
        device.run.assert_called_once_with(["checkbox-cli", "--version"])

    def test_get_version_failure(self, mocker):
        """Test get_version raises error when command fails."""
        device = TrivialDevice()
        device.run = mocker.Mock(return_value=None)

        installer = ConcreteInstaller(device, TrivialDevice())

        with pytest.raises(
            CheckboxInstallerError, match="Unable to retrieve Checkbox version"
        ):
            installer.get_version()

    def test_install_from_source_on_agent(self, mocker):
        """Test installing Checkbox from source on agent."""
        agent = TrivialDevice()
        agent.run = mocker.Mock()
        mock_helper = mocker.Mock()
        mock_helper.get_commit_for_version.return_value = "abc123def456"

        mocker.patch(
            "toolbox.checkbox.installers.CheckboxVersionHelper",
            return_value=mock_helper,
        )

        installer = ConcreteInstaller(TrivialDevice(), agent)
        installer.install_from_source_on_agent("4.0.0.dev42")

        mock_helper.get_commit_for_version.assert_called_once_with("4.0.0.dev42")
        agent.run.assert_called_once_with(
            [
                "pipx",
                "install",
                "git+https://github.com/canonical/checkbox.git@abc123def456#subdirectory=checkbox-ng",
                "--force",
            ]
        )
