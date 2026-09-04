"""Tests for LocalHost device."""

from invoke import Context, Result
from invoke.exceptions import Failure

from toolbox.devices import LocalHost


class TestLocalHostRun:
    """Tests for LocalHost.run() method."""

    def test_run_successful_command(self, mocker):
        """Test running a successful command on localhost."""
        mock_context = mocker.Mock(spec=Context)
        mocker.patch("toolbox.devices.Context", return_value=mock_context)
        expected_result = Result(stdout="hello", exited=0)
        mock_context.run.return_value = expected_result

        device = LocalHost()
        result = device.run("echo hello")

        mock_context.run.assert_called_once_with("echo hello", warn=True)
        assert result is expected_result

    def test_run_command_with_list(self, mocker):
        """Test running a command provided as a list."""
        mock_context = mocker.Mock(spec=Context)
        mocker.patch("toolbox.devices.Context", return_value=mock_context)
        expected_result = Result(stdout="hello world", exited=0)
        mock_context.run.return_value = expected_result

        device = LocalHost()
        result = device.run(["echo", "hello world"])

        # command should be converted to string with proper quoting
        mock_context.run.assert_called_once_with("echo 'hello world'", warn=True)
        assert result is expected_result

    def test_run_failed_command_returns_error_result(self, mocker):
        """Test that failed commands return a Result with exit code 255."""
        mock_context = mocker.Mock(spec=Context)
        mocker.patch("toolbox.devices.Context", return_value=mock_context)
        expected_result = Result(exited=1)
        mock_context.run.side_effect = Failure(expected_result)

        device = LocalHost()
        result = device.run("false")

        assert result.exited == 255
        assert "Command exited with status 1" in result.stderr
