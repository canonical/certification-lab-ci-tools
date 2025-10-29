"""Tests for CheckboxDebsInstaller."""

import pytest

from toolbox.checkbox.installers import CheckboxInstallerError
from toolbox.checkbox.installers.debs import CheckboxDebsInstaller
from toolbox.entities.risk import Risk
from toolbox.interfaces.debs import DebInterface
from toolbox.results import BooleanResult
from tests.devices.trivial import TrivialDevice


class TestCheckboxDebsInstaller:
    """Tests for CheckboxDebsInstaller."""

    def test_add_repositories_success(self, mocker):
        """Test adding repositories successfully."""
        device = TrivialDevice(interfaces=[DebInterface()])
        mock_add_repo = mocker.patch.object(
            device.interfaces[DebInterface],
            "add_repository",
            return_value=BooleanResult(True, message=""),
        )

        installer = CheckboxDebsInstaller(device, TrivialDevice(), Risk.STABLE)
        installer.add_repositories()

        # Should add base repositories + 1 risk-specific
        expected_count = len(CheckboxDebsInstaller.repositories) + 1
        assert mock_add_repo.call_count == expected_count
        calls = [call[0][0] for call in mock_add_repo.call_args_list]
        for repo in CheckboxDebsInstaller.repositories:
            assert repo in calls
        assert "ppa:checkbox-dev/stable" in calls

    def test_add_repositories_with_different_risk(self, mocker):
        """Test adding repositories with different risk level."""
        device = TrivialDevice(interfaces=[DebInterface()])
        mock_add_repo = mocker.patch.object(
            device.interfaces[DebInterface],
            "add_repository",
            return_value=BooleanResult(True, message=""),
        )

        installer = CheckboxDebsInstaller(device, TrivialDevice(), Risk.EDGE)
        installer.add_repositories()

        calls = [call[0][0] for call in mock_add_repo.call_args_list]
        assert "ppa:checkbox-dev/edge" in calls

    def test_add_repositories_failure(self, mocker):
        """Test add_repositories raises error when repository addition fails."""
        device = TrivialDevice(interfaces=[DebInterface()])
        mocker.patch.object(
            device.interfaces[DebInterface],
            "add_repository",
            return_value=BooleanResult(False, message="Repository not found"),
        )

        installer = CheckboxDebsInstaller(device, TrivialDevice(), Risk.STABLE)

        with pytest.raises(
            CheckboxInstallerError, match="Failed to add.*Repository not found"
        ):
            installer.add_repositories()

    def test_install_on_device(self, mocker):
        """Test install_on_device orchestrates all installation steps."""
        device = TrivialDevice(interfaces=[DebInterface()])

        mock_wait = mocker.patch.object(
            device.interfaces[DebInterface], "wait_for_complete"
        )
        mock_add_repos = mocker.patch.object(CheckboxDebsInstaller, "add_repositories")
        mock_install = mocker.patch.object(
            device.interfaces[DebInterface],
            "install",
            return_value=BooleanResult(True, message=""),
        )

        installer = CheckboxDebsInstaller(
            device, TrivialDevice(), Risk.STABLE, providers=["checkbox-provider-custom"]
        )
        installer.install_on_device()

        # Should wait, add repos, install, then wait again
        assert mock_wait.call_count == 2
        mock_add_repos.assert_called_once()
        mock_install.assert_called_once()

        # Verify packages include requirements, providers, and additional providers
        packages = mock_install.call_args[0][0]
        for requirement in CheckboxDebsInstaller.requirements:
            assert requirement in packages
        for provider in CheckboxDebsInstaller.required_providers:
            assert provider in packages
        assert "checkbox-provider-custom" in packages
