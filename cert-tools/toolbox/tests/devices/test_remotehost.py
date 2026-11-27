"""Tests for RemoteHost device."""

import pytest
from fabric import Connection
from invoke import Result
from invoke.exceptions import Failure
from paramiko.ssh_exception import SSHException

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

    @pytest.mark.parametrize("password", [None, "fixture-password"])
    def test_create_connection_sets_channel_timeout(self, password):
        """Bound channel creation without losing password authentication."""
        connection = RemoteHost(
            "example.com", user="ubuntu", password=password
        ).create_connection()
        assert connection.connect_kwargs["channel_timeout"] == 10
        assert connection.connect_kwargs.get("password") == password

    def test_create_connection_returns_connection(self, mocker):
        """Test that create_connection returns a Connection object."""
        mock_connection = mocker.Mock(spec=Connection)
        mocker.patch("toolbox.devices.Connection", return_value=mock_connection)

        device = RemoteHost("example.com", user="ubuntu")
        connection = device.create_connection()

        assert connection is mock_connection


class TestRemoteHostRun:
    """Tests for RemoteHost.run() method."""

    def test_channel_timeout_returns_error_result(self, mocker):
        """A channel-open timeout returns a failed result for status retries."""
        connection = mocker.MagicMock(spec=Connection)
        connection.__enter__.return_value = connection
        connection.__exit__.return_value = False
        connection.run.side_effect = SSHException("Timeout opening channel.")
        mocker.patch.object(RemoteHost, "create_connection", return_value=connection)

        result = RemoteHost("example.com").run(
            ["systemctl", "is-system-running"], hide=True
        )

        assert result.exited == 255
        assert not result
        assert "Timeout opening channel" in result.stderr
        connection.__exit__.assert_called_once()

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


class TestRemoteHostPut:
    """Tests for RemoteHost.put() method."""

    @pytest.fixture
    def connection(self, mocker):
        connection = mocker.MagicMock(spec=Connection)
        connection.__enter__.return_value = connection
        connection.__exit__.return_value = False
        connection.put.side_effect = lambda local, remote, **kwargs: mocker.Mock(
            remote=remote
        )
        mocker.patch.object(RemoteHost, "create_connection", return_value=connection)
        return connection

    def test_copies_files_into_remote_dir_over_one_connection(self, connection):
        """Every file lands in the remote directory under its own name."""
        result = RemoteHost("example.com").put(
            ["/local/retry", "/local/clean_machine"], ".scriptlets"
        )

        RemoteHost.create_connection.assert_called_once()
        assert [call.args for call in connection.put.call_args_list] == [
            ("/local/retry", ".scriptlets/retry"),
            ("/local/clean_machine", ".scriptlets/clean_machine"),
        ]
        assert result.ok
        assert result.stdout.splitlines() == [
            ".scriptlets/retry",
            ".scriptlets/clean_machine",
        ]

    def test_accepts_any_iterable(self, connection):
        """A generator of paths is copied in full, not consumed by logging."""
        paths = (path for path in ["/local/retry", "/local/clean_machine"])

        result = RemoteHost("example.com").put(paths, ".scriptlets")

        assert connection.put.call_count == 2
        assert result.ok

    def test_forwards_transfer_options(self, connection):
        """Extra keyword arguments reach the underlying transfer."""
        RemoteHost("example.com").put(
            ["/local/retry"], ".scriptlets", preserve_mode=False
        )

        assert connection.put.call_args.kwargs == {"preserve_mode": False}

    @pytest.mark.parametrize(
        "error, message",
        [
            (
                FileNotFoundError(2, "No such file or directory", "/local/retry"),
                "/local/retry",
            ),
            (SSHException("Channel closed."), "Channel closed."),
        ],
    )
    def test_transfer_error_returns_failed_result(self, connection, error, message):
        """A failing transfer stops the copy and reports what went wrong."""
        connection.put.side_effect = error

        result = RemoteHost("example.com").put(
            ["/local/retry", "/local/clean_machine"], ".scriptlets"
        )

        assert result.failed
        assert result.exited == 255
        assert message in result.stderr
        connection.put.assert_called_once()
        connection.__exit__.assert_called_once()
