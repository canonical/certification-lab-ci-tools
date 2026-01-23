"""Tests for the toolbox.interfaces.snaps module."""

import pytest

from invoke import Result
from toolbox.interfaces.reboot import RebootInterface
from toolbox.interfaces.snaps import (
    SnapInstallError,
    SnapInterface,
    SnapNotFoundError,
)
from toolbox.interfaces.snapd import SnapdAPIClient, SnapdAPIError
from toolbox.interfaces.status import SystemStatusInterface
from toolbox.results import BooleanResult
from toolbox.retries import Linear

from tests.devices.trivial import TrivialDevice


class TestSnapGets:
    def test_get_active_all_snaps(self, mocker):
        """Test getting all active snaps."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                SnapInterface(),
                RebootInterface(),
                SystemStatusInterface(),
            ]
        )
        expected_result = [{"name": "checkbox", "version": "2.0"}]
        mock_get = mocker.patch.object(
            device.interfaces[SnapdAPIClient], "get", return_value=expected_result
        )

        result = device.interfaces[SnapInterface].get_active()

        assert result == expected_result
        mock_get.assert_called_once_with(endpoint="snaps", params=None)

    def test_get_active_specific_snap(self, mocker):
        """Test getting a specific snap."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                SnapInterface(),
                RebootInterface(),
                SystemStatusInterface(),
            ]
        )
        expected_result = {"name": "checkbox", "version": "2.0"}
        mock_get = mocker.patch.object(
            device.interfaces[SnapdAPIClient], "get", return_value=expected_result
        )

        result = device.interfaces[SnapInterface].get_active("checkbox")

        assert result == expected_result
        mock_get.assert_called_once_with(
            endpoint="snaps", params={"snaps": ["checkbox"]}
        )

    def test_get_changes(self, mocker):
        """Test getting all snap changes."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                SnapInterface(),
                RebootInterface(),
                SystemStatusInterface(),
            ]
        )
        expected_result = [
            {"id": "1", "status": "Done", "ready": True},
            {"id": "2", "status": "Doing", "ready": False},
        ]
        mock_get = mocker.patch.object(
            device.interfaces[SnapdAPIClient], "get", return_value=expected_result
        )

        result = device.interfaces[SnapInterface].get_changes()

        assert result == expected_result
        mock_get.assert_called_once_with(
            endpoint="changes", params={"select": "all"}, timeout=30
        )

    def test_get_change(self, mocker):
        """Test getting a specific change by ID."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                SnapInterface(),
                RebootInterface(),
                SystemStatusInterface(),
            ]
        )
        expected_result = {"id": "123", "status": "Done", "summary": "Install checkbox"}
        mock_get = mocker.patch.object(
            device.interfaces[SnapdAPIClient], "get", return_value=expected_result
        )

        result = device.interfaces[SnapInterface].get_change("123")

        assert result == expected_result
        mock_get.assert_called_once_with(endpoint="changes/123")


class TestCheckSnapChangesComplete:
    """Tests for SnapInterface.check_snap_changes_complete() method."""

    @pytest.mark.parametrize(
        "changes,expected_result,expected_message",
        [
            # All changes ready
            (
                [
                    {"id": "1", "status": "Done", "ready": True},
                    {"id": "2", "status": "Done", "ready": True},
                ],
                True,
                None,
            ),
            # Some changes not ready
            (
                [
                    {
                        "id": "1",
                        "status": "Done",
                        "ready": True,
                        "summary": "Install snap1",
                    },
                    {
                        "id": "2",
                        "status": "Doing",
                        "ready": False,
                        "summary": "Install snap2",
                    },
                ],
                False,
                "Changes: 2",
            ),
            # Multiple changes not ready
            (
                [
                    {
                        "id": "1",
                        "status": "Doing",
                        "ready": False,
                        "summary": "Install snap1",
                    },
                    {
                        "id": "2",
                        "status": "Doing",
                        "ready": False,
                        "summary": "Install snap2",
                    },
                    {
                        "id": "3",
                        "status": "Done",
                        "ready": True,
                        "summary": "Install snap3",
                    },
                ],
                False,
                "Changes: 1, 2",
            ),
            # No changes
            ([], True, None),
        ],
    )
    def test_check_snap_changes_complete(
        self, mocker, changes, expected_result, expected_message
    ):
        """Test checking if snap changes are complete."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                SnapInterface(),
                RebootInterface(),
                SystemStatusInterface(),
            ]
        )
        mock_get_changes = mocker.patch.object(
            device.interfaces[SnapInterface], "get_changes", return_value=changes
        )

        result = device.interfaces[SnapInterface].check_snap_changes_complete()

        assert isinstance(result, BooleanResult)
        assert bool(result) == expected_result
        assert result.message == expected_message
        mock_get_changes.assert_called_once()

    def test_check_snap_changes_complete_with_api_error(self, mocker):
        """Test check_snap_changes_complete when API call fails."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                SnapInterface(),
                RebootInterface(),
                SystemStatusInterface(),
            ]
        )
        mock_get_changes = mocker.patch.object(
            device.interfaces[SnapInterface],
            "get_changes",
            side_effect=SnapdAPIError("Connection failed"),
        )

        result = device.interfaces[SnapInterface].check_snap_changes_complete()

        assert not result
        assert result.message == "Connection failed"
        mock_get_changes.assert_called_once()

    def test_complete_no_reboot_needed(self, mocker):
        """Test when changes are complete and no reboot is needed."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                SnapInterface(),
                RebootInterface(),
                SystemStatusInterface(),
            ]
        )
        mock_check = mocker.patch.object(
            device.interfaces[SnapInterface],
            "check_snap_changes_complete",
            return_value=BooleanResult(True),
        )

        result = device.interfaces[
            SnapInterface
        ].check_snap_changes_complete_and_reboot()

        assert result
        mock_check.assert_called_once()

    def test_incomplete_no_reboot_needed(self, mocker):
        """Test when changes are incomplete but no reboot is needed."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                SnapInterface(),
                RebootInterface(),
                SystemStatusInterface(),
            ]
        )
        mock_check = mocker.patch.object(
            device.interfaces[SnapInterface],
            "check_snap_changes_complete",
            return_value=BooleanResult(False, "Changes: 1"),
        )
        mock_is_reboot_required = mocker.patch.object(
            device.interfaces[RebootInterface], "is_reboot_required", return_value=False
        )

        result = device.interfaces[
            SnapInterface
        ].check_snap_changes_complete_and_reboot()

        assert not result
        assert result.message == "Changes: 1"
        mock_check.assert_called_once()
        mock_is_reboot_required.assert_called_once()

    def test_incomplete_reboot_and_complete(self, mocker):
        """Test when changes are incomplete, reboot happens, then complete."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                SnapInterface(),
                RebootInterface(),
                SystemStatusInterface(),
            ]
        )
        mock_check = mocker.patch.object(
            device.interfaces[SnapInterface],
            "check_snap_changes_complete",
            side_effect=[
                BooleanResult(False, "Changes: 1"),
                BooleanResult(True),
            ],
        )
        mock_is_reboot_required = mocker.patch.object(
            device.interfaces[RebootInterface], "is_reboot_required", return_value=True
        )
        mock_reboot = mocker.patch.object(device.interfaces[RebootInterface], "reboot")
        mock_wait = mocker.patch.object(
            device.interfaces[SystemStatusInterface],
            "wait_for_status",
            return_value=BooleanResult(True),
        )

        result = device.interfaces[
            SnapInterface
        ].check_snap_changes_complete_and_reboot()

        assert result
        assert mock_check.call_count == 2
        mock_is_reboot_required.assert_called_once()
        mock_reboot.assert_called_once()
        mock_wait.assert_called_once_with(allowed={"degraded"}, policy=None)

    def test_incomplete_reboot_with_status_policy(self, mocker):
        """Test reboot with custom status policy."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                SnapInterface(),
                RebootInterface(),
                SystemStatusInterface(),
            ]
        )
        mocker.patch.object(
            device.interfaces[SnapInterface],
            "check_snap_changes_complete",
            side_effect=[
                BooleanResult(False, "Changes: 1"),
                BooleanResult(True),
            ],
        )
        mocker.patch.object(
            device.interfaces[RebootInterface], "is_reboot_required", return_value=True
        )
        mocker.patch.object(device.interfaces[RebootInterface], "reboot")
        mock_wait = mocker.patch.object(
            device.interfaces[SystemStatusInterface],
            "wait_for_status",
            return_value=BooleanResult(True),
        )
        status_policy = Linear(times=5, delay=1.0)

        result = device.interfaces[
            SnapInterface
        ].check_snap_changes_complete_and_reboot(status_policy=status_policy)

        assert result
        mock_wait.assert_called_once_with(allowed={"degraded"}, policy=status_policy)


class TestWaitForSnapChanges:
    """Tests for SnapInterface.wait_for_snap_changes() method."""

    def test_wait_for_snap_changes_immediate_success(self, mocker):
        """Test wait_for_snap_changes when changes complete immediately."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                SnapInterface(),
                RebootInterface(),
                SystemStatusInterface(),
            ]
        )
        mock_check = mocker.patch.object(
            device.interfaces[SnapInterface],
            "check_snap_changes_complete_and_reboot",
            return_value=BooleanResult(True),
            __name__="check_snap_changes_complete_and_reboot",
        )

        result = device.interfaces[SnapInterface].wait_for_snap_changes()

        assert result
        mock_check.assert_called_once()

    def test_wait_for_snap_changes_with_retries(self, mocker):
        """Test wait_for_snap_changes with retries."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                SnapInterface(),
                RebootInterface(),
                SystemStatusInterface(),
            ]
        )
        mock_check = mocker.patch.object(
            device.interfaces[SnapInterface],
            "check_snap_changes_complete_and_reboot",
            side_effect=[
                BooleanResult(False, "Changes: 1"),
                BooleanResult(False, "Changes: 1"),
                BooleanResult(True),
            ],
            __name__="check_snap_changes_complete_and_reboot",
        )
        policy = Linear(times=3, delay=0)

        result = device.interfaces[SnapInterface].wait_for_snap_changes(policy=policy)

        assert result
        assert mock_check.call_count == 3

    def test_wait_for_snap_changes_exhausts_retries(self, mocker):
        """Test wait_for_snap_changes when retries are exhausted."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                SnapInterface(),
                RebootInterface(),
                SystemStatusInterface(),
            ]
        )
        mock_check = mocker.patch.object(
            device.interfaces[SnapInterface],
            "check_snap_changes_complete_and_reboot",
            return_value=BooleanResult(False, "Changes: 1"),
            __name__="check_snap_changes_complete_and_reboot",
        )
        policy = Linear(times=2, delay=0)

        result = device.interfaces[SnapInterface].wait_for_snap_changes(policy=policy)

        assert not result
        # initial attempt + 2 retries = 3 total calls
        assert mock_check.call_count == 3


class TestInstall:
    """Tests for SnapInterface.install() method."""

    def test_install_snap_success(self, mocker):
        """Test successful snap installation."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                SnapInterface(),
                RebootInterface(),
                SystemStatusInterface(),
            ]
        )
        mock_get_active = mocker.patch.object(
            device.interfaces[SnapInterface], "get_active", return_value=None
        )
        device.run = mocker.Mock(
            return_value=Result(stdout="123\n", stderr="", exited=0)
        )
        mock_wait = mocker.patch.object(
            device.interfaces[SnapInterface],
            "wait_for_snap_changes",
            return_value=BooleanResult(True),
        )
        mock_get_change = mocker.patch.object(
            device.interfaces[SnapInterface],
            "get_change",
            return_value={"id": "123", "status": "Done", "summary": "Install checkbox"},
        )

        device.interfaces[SnapInterface].install("checkbox")
        mock_get_active.assert_called_once_with("checkbox")
        device.run.assert_called_once_with(
            ["sudo", "snap", "install", "--no-wait", "checkbox"], hide=True
        )
        mock_wait.assert_called_once()
        mock_get_change.assert_called_once_with("123")

    def test_install_snap_with_channel(self, mocker):
        """Test installing snap with specific channel."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                SnapInterface(),
                RebootInterface(),
                SystemStatusInterface(),
            ]
        )
        mocker.patch.object(
            device.interfaces[SnapInterface], "get_active", return_value=None
        )
        device.run = mocker.Mock(
            return_value=Result(stdout="123\n", stderr="", exited=0)
        )
        mocker.patch.object(
            device.interfaces[SnapInterface],
            "wait_for_snap_changes",
            return_value=BooleanResult(True),
        )
        mocker.patch.object(
            device.interfaces[SnapInterface],
            "get_change",
            return_value={"id": "123", "status": "Done", "summary": "Install checkbox"},
        )

        device.interfaces[SnapInterface].install("checkbox", channel="edge")
        device.run.assert_called_once_with(
            ["sudo", "snap", "install", "--no-wait", "checkbox", "--channel=edge"],
            hide=True,
        )

    def test_install_snap_with_options(self, mocker):
        """Test installing snap with additional options."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                SnapInterface(),
                RebootInterface(),
                SystemStatusInterface(),
            ]
        )
        mocker.patch.object(
            device.interfaces[SnapInterface], "get_active", return_value=None
        )
        device.run = mocker.Mock(
            return_value=Result(stdout="123\n", stderr="", exited=0)
        )
        mocker.patch.object(
            device.interfaces[SnapInterface],
            "wait_for_snap_changes",
            return_value=BooleanResult(True),
        )
        mocker.patch.object(
            device.interfaces[SnapInterface],
            "get_change",
            return_value={"id": "123", "status": "Done", "summary": "Install checkbox"},
        )

        device.interfaces[SnapInterface].install(
            "checkbox", options=["--classic", "--dangerous"]
        )
        device.run.assert_called_once_with(
            [
                "sudo",
                "snap",
                "install",
                "--no-wait",
                "checkbox",
                "--classic",
                "--dangerous",
            ],
            hide=True,
        )

    def test_install_snap_already_installed_refresh(self, mocker):
        """Test installing snap when already installed triggers refresh."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                SnapInterface(),
                RebootInterface(),
                SystemStatusInterface(),
            ]
        )
        mocker.patch.object(
            device.interfaces[SnapInterface],
            "get_active",
            return_value={"name": "checkbox", "version": "1.0"},
        )
        device.run = mocker.Mock(
            return_value=Result(stdout="123\n", stderr="", exited=0)
        )
        mocker.patch.object(
            device.interfaces[SnapInterface],
            "wait_for_snap_changes",
            return_value=BooleanResult(True),
        )
        mocker.patch.object(
            device.interfaces[SnapInterface],
            "get_change",
            return_value={"id": "123", "status": "Done", "summary": "Refresh checkbox"},
        )

        device.interfaces[SnapInterface].install("checkbox", refresh_ok=True)
        device.run.assert_called_once_with(
            ["sudo", "snap", "refresh", "--no-wait", "checkbox"], hide=True
        )

    def test_install_snap_no_change_id(self, mocker):
        """Test installing snap when no change ID is returned (already up to date)."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                SnapInterface(),
                RebootInterface(),
                SystemStatusInterface(),
            ]
        )
        mock_get_active = mocker.patch.object(
            device.interfaces[SnapInterface], "get_active", return_value=None
        )
        device.run = mocker.Mock(return_value=Result(stdout="", stderr="", exited=0))

        device.interfaces[SnapInterface].install("checkbox")
        mock_get_active.assert_called_once_with("checkbox")

    def test_install_snap_not_found(self, mocker):
        """Test installing snap that is not found."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                SnapInterface(),
                RebootInterface(),
                SystemStatusInterface(),
            ]
        )
        mock_get_active = mocker.patch.object(
            device.interfaces[SnapInterface], "get_active", return_value=None
        )
        device.run = mocker.Mock(
            return_value=Result(stdout="", stderr="error: snap not found", exited=1)
        )

        with pytest.raises(SnapNotFoundError, match="not found"):
            device.interfaces[SnapInterface].install("nonexistent")

        mock_get_active.assert_called_once_with("nonexistent")

    def test_install_snap_command_fails(self, mocker):
        """Test installing snap when command fails."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                SnapInterface(),
                RebootInterface(),
                SystemStatusInterface(),
            ]
        )
        mocker.patch.object(
            device.interfaces[SnapInterface], "get_active", return_value=None
        )
        device.run = mocker.Mock(
            return_value=Result(stdout="", stderr="error: permission denied", exited=1)
        )

        with pytest.raises(SnapInstallError, match="permission denied"):
            device.interfaces[SnapInterface].install("checkbox")

    def test_install_snap_wait_timeout(self, mocker):
        """Test installing snap when wait times out."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                SnapInterface(),
                RebootInterface(),
                SystemStatusInterface(),
            ]
        )
        mocker.patch.object(
            device.interfaces[SnapInterface], "get_active", return_value=None
        )
        device.run = mocker.Mock(
            return_value=Result(stdout="123\n", stderr="", exited=0)
        )
        mock_wait = mocker.patch.object(
            device.interfaces[SnapInterface],
            "wait_for_snap_changes",
            return_value=BooleanResult(False, "Timeout"),
        )
        mocker.patch.object(
            device.interfaces[SnapInterface],
            "get_change",
            return_value={
                "id": "123",
                "status": "Doing",
                "summary": "Install checkbox",
            },
        )

        with pytest.raises(SnapInstallError, match="timed-out"):
            device.interfaces[SnapInterface].install("checkbox")

        mock_wait.assert_called_once()

    def test_install_snap_change_incomplete(self, mocker):
        """Test installing snap when change doesn't complete successfully."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                SnapInterface(),
                RebootInterface(),
                SystemStatusInterface(),
            ]
        )
        mocker.patch.object(
            device.interfaces[SnapInterface], "get_active", return_value=None
        )
        device.run = mocker.Mock(
            return_value=Result(stdout="123\n", stderr="", exited=0)
        )
        mocker.patch.object(
            device.interfaces[SnapInterface],
            "wait_for_snap_changes",
            return_value=BooleanResult(True),
        )
        mocker.patch.object(
            device.interfaces[SnapInterface],
            "get_change",
            return_value={
                "id": "123",
                "status": "Error",
                "summary": "Install checkbox",
            },
        )

        with pytest.raises(SnapInstallError, match="incomplete"):
            device.interfaces[SnapInterface].install("checkbox")

    def test_install_with_custom_policy(self, mocker):
        """Test installing snap with custom retry policy."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                SnapInterface(),
                RebootInterface(),
                SystemStatusInterface(),
            ]
        )
        mocker.patch.object(
            device.interfaces[SnapInterface], "get_active", return_value=None
        )
        device.run = mocker.Mock(
            return_value=Result(stdout="123\n", stderr="", exited=0)
        )
        mock_wait = mocker.patch.object(
            device.interfaces[SnapInterface],
            "wait_for_snap_changes",
            return_value=BooleanResult(True),
        )
        mocker.patch.object(
            device.interfaces[SnapInterface],
            "get_change",
            return_value={"id": "123", "status": "Done", "summary": "Install checkbox"},
        )
        policy = Linear(times=10, delay=2.0)

        device.interfaces[SnapInterface].install("checkbox", policy=policy)
        mock_wait.assert_called_once_with(policy=policy)
