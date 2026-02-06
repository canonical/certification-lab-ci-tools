"""Tests for the toolbox.interfaces.status module."""

import pytest

from invoke import Result
from toolbox.interfaces.status import SystemStatusInterface
from toolbox.results import BooleanResult
from toolbox.retries import Linear

from tests.devices.trivial import TrivialDevice


class TestGetStatus:
    """Tests for SystemStatusInterface.get_status() method."""

    @pytest.mark.parametrize(
        "stdout,allowed,expected_result,expected_message",
        [
            # Basic cases with default allowed set (only 'running')
            ("running\n", None, True, "running"),
            ("degraded\n", None, False, "degraded"),
            ("starting\n", None, False, "starting"),
            ("initializing\n", None, False, "initializing"),
            ("maintenance\n", None, False, "maintenance"),
            ("stopping\n", None, False, "stopping"),
            # Custom allowed states
            ("degraded\n", ["degraded"], True, "degraded"),
            ("starting\n", ["starting", "degraded"], True, "starting"),
            # 'running' is always in the allowed set
            ("running\n", ["degraded"], True, "running"),
            ("running\n", ["starting", "degraded"], True, "running"),
        ],
    )
    def test_get_status(
        self, mocker, stdout, allowed, expected_result, expected_message
    ):
        """Test get_status with various system states and allowed sets."""
        device = TrivialDevice(interfaces=[SystemStatusInterface()])
        device.run = mocker.Mock(return_value=Result(stdout=stdout, exited=0))

        result = device.interfaces[SystemStatusInterface].get_status(allowed=allowed)

        assert result is not None
        assert isinstance(result, BooleanResult)
        assert bool(result) == expected_result
        assert result.message == expected_message
        device.run.assert_called_once_with(
            command=["systemctl", "is-system-running"], hide=True
        )

    def test_get_status_returns_false_on_execution_error(self, mocker):
        """Test that get_status returns False when command execution fails."""
        device = TrivialDevice(interfaces=[SystemStatusInterface()])
        # Mock a failed Result (not ok)
        device.run = mocker.Mock(
            return_value=Result(
                command="systemctl is-system-running",
                exited=255,
                stderr="SSH connection failed",
            )
        )

        result = device.interfaces[SystemStatusInterface].get_status()

        assert not result
        assert result.message is None

    def test_get_status_handles_empty_stdout(self, mocker):
        """Test that get_status handles empty stdout gracefully."""
        device = TrivialDevice(interfaces=[SystemStatusInterface()])
        device.run = mocker.Mock(return_value=Result(stdout="", exited=255))

        result = device.interfaces[SystemStatusInterface].get_status()

        # When stdout is empty, should return False
        assert not result
        assert result.message is None


class TestWaitForStatus:
    """Tests for SystemStatusInterface.wait_for_status() method."""

    @pytest.mark.parametrize(
        "results,allowed,policy,expected_result,expected_message,expected_call_count",
        [
            # Immediate success with default allowed set
            (
                [Result(stdout="running\n", exited=0)],
                None,
                None,
                True,
                "running",
                1,
            ),
            # Immediate success with custom allowed state
            (
                [Result(stdout="degraded\n", exited=0)],
                ["degraded"],
                None,
                True,
                "degraded",
                1,
            ),
            # Retry until success
            (
                [
                    Result(stdout="starting\n", exited=1),
                    Result(stdout="starting\n", exited=1),
                    Result(stdout="running\n", exited=0),
                ],
                None,
                Linear(times=3, delay=0),
                True,
                "running",
                3,
            ),
            # Exhaust retries
            (
                [
                    Result(stdout="starting\n", exited=1),
                    Result(stdout="starting\n", exited=1),
                    Result(stdout="starting\n", exited=1),
                ],
                None,
                Linear(times=2, delay=0),
                False,
                "starting",
                3,  # initial attempt + 2 retries
            ),
            # Default policy (infinite retries)
            (
                [
                    Result(stdout="starting\n", exited=1),
                    Result(stdout="running\n", exited=0),
                ],
                None,
                None,
                True,
                "running",
                2,
            ),
        ],
    )
    def test_wait_for_status(
        self,
        mocker,
        results,
        allowed,
        policy,
        expected_result,
        expected_message,
        expected_call_count,
    ):
        """Test wait_for_status with various retry scenarios."""
        device = TrivialDevice(interfaces=[SystemStatusInterface()])
        device.run = mocker.Mock(side_effect=results)

        result = device.interfaces[SystemStatusInterface].wait_for_status(
            allowed=allowed, policy=policy
        )

        assert bool(result) == expected_result
        assert result.message == expected_message
        assert device.run.call_count == expected_call_count

    @pytest.mark.parametrize(
        "side_effects,allowed,policy,expected_result,expected_message,expected_call_count",
        [
            # Execution errors then success
            (
                [
                    Result(command="cmd", exited=255, stderr="SSH connection failed"),
                    Result(command="cmd", exited=255, stderr="SSH connection failed"),
                    Result(stdout="running\n", exited=0),
                ],
                None,
                Linear(times=3, delay=0),
                True,
                "running",
                3,
            ),
            # Empty output then success
            (
                [
                    Result(stdout="", exited=1),
                    Result(stdout="", exited=1),
                    Result(stdout="running\n", exited=0),
                ],
                None,
                Linear(times=3, delay=0),
                True,
                "running",
                3,
            ),
            # Mixed errors and empty output then success
            (
                [
                    Result(command="cmd", exited=255, stderr="SSH connection failed"),
                    Result(stdout="", exited=1),
                    Result(command="cmd", exited=255, stderr="SSH connection failed"),
                    Result(stdout="starting\n", exited=1),
                    Result(stdout="running\n", exited=0),
                ],
                None,
                Linear(times=5, delay=0),
                True,
                "running",
                5,
            ),
            # Exhaust retries with only errors
            (
                [
                    Result(command="cmd", exited=255, stderr="SSH connection failed"),
                    Result(command="cmd", exited=255, stderr="SSH connection failed"),
                    Result(command="cmd", exited=255, stderr="SSH connection failed"),
                ],
                None,
                Linear(times=2, delay=0),
                False,
                None,
                3,  # initial attempt + 2 retries
            ),
        ],
    )
    def test_wait_for_status_with_errors(
        self,
        mocker,
        side_effects,
        allowed,
        policy,
        expected_result,
        expected_message,
        expected_call_count,
    ):
        """Test wait_for_status with execution errors and empty output."""
        device = TrivialDevice(interfaces=[SystemStatusInterface()])
        device.run = mocker.Mock(side_effect=side_effects)

        result = device.interfaces[SystemStatusInterface].wait_for_status(
            allowed=allowed, policy=policy
        )

        assert bool(result) == expected_result
        assert result.message == expected_message
        assert device.run.call_count == expected_call_count

    @pytest.mark.parametrize(
        "results,policy,expected_sleep_count,expected_delays",
        [
            # No sleep on immediate success
            (
                [Result(stdout="running\n", exited=0)],
                Linear(times=3, delay=1.0),
                0,
                [],
            ),
            # Sleep between retry attempts
            (
                [
                    Result(stdout="starting\n", exited=1),
                    Result(stdout="starting\n", exited=1),
                    Result(stdout="running\n", exited=0),
                ],
                Linear(times=3, delay=0.5),
                2,
                [0.5, 0.5],
            ),
        ],
    )
    def test_wait_for_status_sleep_behavior(
        self, mocker, results, policy, expected_sleep_count, expected_delays
    ):
        """Test that wait_for_status sleeps correctly between retry attempts."""
        mock_sleep = mocker.patch("toolbox.retries.sleep")
        device = TrivialDevice(interfaces=[SystemStatusInterface()])
        device.run = mocker.Mock(side_effect=results)

        result = device.interfaces[SystemStatusInterface].wait_for_status(policy=policy)

        assert result
        assert mock_sleep.call_count == expected_sleep_count
        if expected_delays:
            mock_sleep.assert_has_calls(
                [mocker.call(delay) for delay in expected_delays]
            )
