"""Tests for the toolbox.interfaces.debs module."""

from invoke import Result

from toolbox.interfaces.debs import DebInterface
from toolbox.retries import Linear
from tests.devices.trivial import TrivialDevice


class TestDebAction:
    """Tests for DebInterface.action() method."""

    def test_action_successful(self, mocker):
        """Test action returns True when command succeeds."""
        device = TrivialDevice(interfaces=[DebInterface()])
        device.run = mocker.Mock(return_value=Result(stdout="", exited=0))

        result = device.interfaces[DebInterface].action("update")

        assert result is True
        expected_command = [
            "sudo",
            "DEBIAN_FRONTEND=noninteractive",
            "apt-get",
            "-qqy",
            "-o",
            "Dpkg::Options::=--force-confdef",
            "-o",
            "Dpkg::Options::=--force-confold",
            "update",
        ]
        device.run.assert_called_once_with(expected_command)

    def test_action_fails(self, mocker):
        """Test action returns False when command fails."""
        device = TrivialDevice(interfaces=[DebInterface()])
        device.run = mocker.Mock(return_value=Result(stdout="", exited=1))

        result = device.interfaces[DebInterface].action("update")

        assert result is False

    def test_action_with_options(self, mocker):
        """Test action includes additional options before the action."""
        device = TrivialDevice(interfaces=[DebInterface()])
        device.run = mocker.Mock(return_value=Result(stdout="", exited=0))

        result = device.interfaces[DebInterface].action(
            "install", options=["--allow-downgrades"]
        )

        assert result is True
        expected_command = [
            "sudo",
            "DEBIAN_FRONTEND=noninteractive",
            "apt-get",
            "-qqy",
            *DebInterface.options,
            "--allow-downgrades",
            "install",
        ]
        device.run.assert_called_once_with(expected_command)

    def test_action_with_action_options(self, mocker):
        """Test action includes action_options after the action."""
        device = TrivialDevice(interfaces=[DebInterface()])
        device.run = mocker.Mock(return_value=Result(stdout="", exited=0))

        result = device.interfaces[DebInterface].action(
            "install", action_options=["package1", "package2"]
        )

        assert result is True
        expected_command = [
            "sudo",
            "DEBIAN_FRONTEND=noninteractive",
            "apt-get",
            "-qqy",
            *DebInterface.options,
            "install",
            "package1",
            "package2",
        ]
        device.run.assert_called_once_with(expected_command)

    def test_action_with_both_options(self, mocker):
        """Test action includes both options and action_options."""
        device = TrivialDevice(interfaces=[DebInterface()])
        device.run = mocker.Mock(return_value=Result(stdout="", exited=0))

        result = device.interfaces[DebInterface].action(
            "install",
            options=["--allow-downgrades"],
            action_options=["package1", "package2"],
        )

        assert result is True
        expected_command = [
            "sudo",
            "DEBIAN_FRONTEND=noninteractive",
            "apt-get",
            "-qqy",
            *DebInterface.options,
            "--allow-downgrades",
            "install",
            "package1",
            "package2",
        ]
        device.run.assert_called_once_with(expected_command)


class TestDebPackageOperations:
    """Tests for DebInterface package management methods."""

    def test_update(self, mocker):
        """Test update calls action with 'update'."""
        device = TrivialDevice(interfaces=[DebInterface()])
        device.run = mocker.Mock(return_value=Result(stdout="", exited=0))

        result = device.interfaces[DebInterface].update()

        assert result is True
        call_args = device.run.call_args[0][0]
        assert call_args[-1] == "update"

    def test_upgrade(self, mocker):
        """Test upgrade calls action with 'dist-upgrade'."""
        device = TrivialDevice(interfaces=[DebInterface()])
        device.run = mocker.Mock(return_value=Result(stdout="", exited=0))

        result = device.interfaces[DebInterface].upgrade()

        assert result is True
        call_args = device.run.call_args[0][0]
        assert call_args[-1] == "dist-upgrade"

    def test_upgrade_with_options(self, mocker):
        """Test upgrade with additional options."""
        device = TrivialDevice(interfaces=[DebInterface()])
        device.run = mocker.Mock(return_value=Result(stdout="", exited=0))

        result = device.interfaces[DebInterface].upgrade(options=["--allow-downgrades"])

        assert result is True
        call_args = device.run.call_args[0][0]
        assert "--allow-downgrades" in call_args
        assert call_args[-1] == "dist-upgrade"

    def test_install(self, mocker):
        """Test install calls action with package names."""
        device = TrivialDevice(interfaces=[DebInterface()])
        device.run = mocker.Mock(return_value=Result(stdout="", exited=0))

        result = device.interfaces[DebInterface].install(["package1", "package2"])

        assert result is True
        call_args = device.run.call_args[0][0]
        assert call_args[-3:] == ["install", "package1", "package2"]

    def test_install_with_options(self, mocker):
        """Test install with additional options."""
        device = TrivialDevice(interfaces=[DebInterface()])
        device.run = mocker.Mock(return_value=Result(stdout="", exited=0))

        result = device.interfaces[DebInterface].install(
            ["package1"], options=["--no-install-recommends"]
        )

        assert result is True
        call_args = device.run.call_args[0][0]
        assert "--no-install-recommends" in call_args
        assert call_args[-2:] == ["install", "package1"]


class TestDebCompletionChecks:
    """Tests for DebInterface completion checking methods."""

    def test_are_package_processes_ongoing_returns_result(self, mocker):
        """Test are_package_processes_ongoing returns the command result."""
        device = TrivialDevice(interfaces=[DebInterface()])
        expected_result = Result(stdout="123 apt-get\n456 dpkg\n", exited=0)
        device.run = mocker.Mock(return_value=expected_result)

        result = device.interfaces[DebInterface].are_package_processes_ongoing()

        assert result is expected_result
        device.run.assert_called_once_with(
            ["pgrep", "--list-full", "^apt|dpkg"], hide=True
        )

    def test_are_package_files_open_returns_result(self, mocker):
        """Test are_package_files_open returns the command result."""
        device = TrivialDevice(interfaces=[DebInterface()])
        expected_result = Result(stdout="", stderr="/var/lib/dpkg/lock: 123", exited=0)
        device.run = mocker.Mock(return_value=expected_result)

        result = device.interfaces[DebInterface].are_package_files_open()

        assert result is expected_result
        device.run.assert_called_once_with(
            ["sudo", "fuser"] + DebInterface.files, hide=True
        )

    def test_check_complete_returns_true_when_no_operations(self, mocker):
        """Test check_complete returns True when no package operations ongoing."""
        device = TrivialDevice(interfaces=[DebInterface()])
        device.run = mocker.Mock(return_value=Result(stdout="", exited=1))

        result = device.interfaces[DebInterface].check_complete()

        assert result is True
        assert device.run.call_count == 2

    def test_check_complete_returns_false_when_processes_running(self, mocker):
        """Test check_complete returns False when processes are running."""
        device = TrivialDevice(interfaces=[DebInterface()])
        device.run = mocker.Mock(
            side_effect=[
                Result(stdout="123 apt-get\n", exited=0),  # processes ongoing
                Result(stdout="", exited=1),  # no files open
            ]
        )

        result = device.interfaces[DebInterface].check_complete()

        assert result is False
        assert device.run.call_count == 2

    def test_check_complete_returns_false_when_files_open(self, mocker):
        """Test check_complete returns False when package files are open."""
        device = TrivialDevice(interfaces=[DebInterface()])
        device.run = mocker.Mock(
            side_effect=[
                Result(stdout="", exited=1),  # no processes
                Result(
                    stdout="", stderr="/var/lib/dpkg/lock: 123", exited=0
                ),  # files open
            ]
        )

        result = device.interfaces[DebInterface].check_complete()

        assert result is False
        assert device.run.call_count == 2

    def test_check_complete_returns_false_when_both_ongoing(self, mocker):
        """Test check_complete returns False when both processes and files ongoing."""
        device = TrivialDevice(interfaces=[DebInterface()])
        device.run = mocker.Mock(
            side_effect=[
                Result(stdout="123 apt-get\n", exited=0),  # processes ongoing
                Result(
                    stdout="", stderr="/var/lib/dpkg/lock: 123", exited=0
                ),  # files open
            ]
        )

        result = device.interfaces[DebInterface].check_complete()

        assert result is False
        assert device.run.call_count == 2

    def test_wait_for_complete_returns_true_immediately(self, mocker):
        """Test wait_for_complete returns True when operations complete immediately."""
        device = TrivialDevice(interfaces=[DebInterface()])
        device.run = mocker.Mock(return_value=Result(stdout="", exited=1))

        result = device.interfaces[DebInterface].wait_for_complete()

        assert result is True

    def test_wait_for_complete_retries_until_success(self, mocker):
        """Test wait_for_complete retries until operations complete."""
        device = TrivialDevice(interfaces=[DebInterface()])
        # First two calls: processes running, then no files
        # Next two calls: processes running, then no files
        # Last two calls: no processes, no files (complete)
        device.run = mocker.Mock(
            side_effect=[
                Result(stdout="123 apt-get\n", exited=0),
                Result(stdout="", exited=1),
                Result(stdout="123 apt-get\n", exited=0),
                Result(stdout="", exited=1),
                Result(stdout="", exited=1),
                Result(stdout="", exited=1),
            ]
        )

        policy = Linear(times=3, delay=0)
        result = device.interfaces[DebInterface].wait_for_complete(policy=policy)

        assert result is True
        # 2 checks per attempt * 3 attempts = 6 calls
        assert device.run.call_count == 6

    def test_wait_for_complete_exhausts_retries(self, mocker):
        """Test wait_for_complete returns False when retries exhausted."""
        device = TrivialDevice(interfaces=[DebInterface()])
        # Always return processes running
        device.run = mocker.Mock(
            side_effect=[
                Result(stdout="123 apt-get\n", exited=0),
                Result(stdout="", exited=1),
                Result(stdout="123 apt-get\n", exited=0),
                Result(stdout="", exited=1),
                Result(stdout="123 apt-get\n", exited=0),
                Result(stdout="", exited=1),
            ]
        )

        policy = Linear(times=2, delay=0)
        result = device.interfaces[DebInterface].wait_for_complete(policy=policy)

        assert result is False
        # 2 checks per attempt * 3 attempts (initial + 2 retries) = 6 calls
        assert device.run.call_count == 6
