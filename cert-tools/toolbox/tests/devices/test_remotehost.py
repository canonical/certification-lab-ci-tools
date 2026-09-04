"""Tests for RemoteHost device."""

from fabric import Connection
from invoke import Result
from invoke.exceptions import Failure

from toolbox.devices import RemoteHost


class TestRemoteHostInitialization:
    """Tests for RemoteHost initialization."""

    def test_init_with_host_only(self):
        """Test creating a remote host with only a hostname."""
        device = RemoteHost("example.com")
        assert device.host == "example.com"
        assert device.user is None
        assert device.config is None

    def test_init_with_user(self):
        """Test creating a remote host with a username."""
        device = RemoteHost("example.com", user="ubuntu")
        assert device.host == "example.com"
        assert device.user == "ubuntu"


class TestRemoteHostConnection:
    """Tests for RemoteHost.create_connection() method."""

    def test_create_connection_returns_connection(self, mocker):
        """Test that create_connection returns a Connection object."""
        mock_connection = mocker.Mock(spec=Connection)
        mocker.patch("toolbox.devices.Connection", return_value=mock_connection)

        device = RemoteHost("example.com", user="ubuntu")
        connection = device.create_connection()

        assert connection is mock_connection


class TestRemoteHostRun:
    """Tests for RemoteHost.run() method."""

    def test_run_successful_command(self, mocker):
        """Test running a successful command on a remote host."""
        mock_connection = mocker.Mock(spec=Connection)
        result = Result(stdout="hello", exited=0)
        mock_connection.run.return_value = result
        mock_connection.__enter__ = mocker.Mock(return_value=mock_connection)
        mock_connection.__exit__ = mocker.Mock(return_value=False)

        mocker.patch.object(
            RemoteHost, "create_connection", return_value=mock_connection
        )

        device = RemoteHost("example.com")
        device_result = device.run("echo hello")

        mock_connection.run.assert_called_once_with("echo hello", warn=True)
        assert device_result is result

    def test_run_command_with_list(self, mocker):
        """Test running a command provided as a list."""
        mock_connection = mocker.Mock(spec=Connection)
        result = Result(stdout="hello world", exited=0)
        mock_connection.run.return_value = result
        mock_connection.__enter__ = mocker.Mock(return_value=mock_connection)
        mock_connection.__exit__ = mocker.Mock(return_value=False)

        mocker.patch.object(
            RemoteHost, "create_connection", return_value=mock_connection
        )

        device = RemoteHost("example.com")
        device_result = device.run(["echo", "hello world"])

        # command should be converted to string with proper quoting
        mock_connection.run.assert_called_once_with("echo 'hello world'", warn=True)
        assert device_result is result

    def test_run_failed_command_returns_error_result(self, mocker):
        """Test that failed commands return a Result with exit code 255."""
        mock_connection = mocker.Mock(spec=Connection)
        mock_result = Result(exited=1)
        original_error = Failure(mock_result)
        mock_connection.run.side_effect = original_error
        mock_connection.__enter__ = mocker.Mock(return_value=mock_connection)
        mock_connection.__exit__ = mocker.Mock(return_value=False)

        mocker.patch.object(
            RemoteHost, "create_connection", return_value=mock_connection
        )

        device = RemoteHost("example.com")
        result = device.run("false")

        assert result.exited == 255
        assert result.command == "false"
