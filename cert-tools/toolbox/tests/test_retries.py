"""Tests for the toolbox.retries module."""

from toolbox.retries import Linear, RetryPolicy, retry


class TestLinearRetryPolicy:
    """Tests for the Linear retry policy."""

    def test_finite_retries_generates_correct_waits(self):
        """Test that Linear generates the correct number of wait times."""
        policy = Linear(times=3, delay=1.5)
        waits = list(policy.waits())
        assert waits == [1.5, 1.5, 1.5]

    def test_infinite_retries_generates_unlimited_waits(self):
        """Test that Linear with no times limit generates waits indefinitely."""
        policy = Linear(delay=2.0)
        waits_iter = policy.waits()
        # check first 100 values
        for _ in range(100):
            assert next(waits_iter) == 2.0

    def test_default_delay(self):
        """Test that Linear uses default delay of 0 when not specified."""
        policy = Linear(times=2)
        waits = list(policy.waits())
        assert waits == [0, 0]

    def test_default_values(self):
        """Test Linear with default parameters."""
        policy = Linear()
        waits_iter = policy.waits()
        # with times=None and delay=0 (default), should generate infinite zeros
        for _ in range(100):
            assert next(waits_iter) == 0


class TestRetryFunction:
    """Tests for the retry function."""

    def test_script_succeeds_immediately(self, mocker):
        """Test that retry returns immediately if script succeeds."""
        script = mocker.Mock(return_value="success")
        result = retry(script)

        assert result == "success"
        assert script.call_count == 1

    def test_script_fails_then_succeeds(self, mocker):
        """Test that retry retries until script succeeds."""
        script = mocker.Mock(
            side_effect=[False, False, "success"], __name__="test_script"
        )
        policy = Linear(times=3, delay=0)

        result = retry(script, policy=policy)

        assert result == "success"
        assert script.call_count == 3

    def test_script_exhausts_retries(self, mocker):
        """Test that retry stops after policy is exhausted."""
        script = mocker.Mock(return_value=False)
        policy = Linear(times=3, delay=0)

        result = retry(script, policy=policy)

        assert result is False
        # initial attempt + 3 retries = 4 total calls
        assert script.call_count == 4

    def test_script_returns_truthy_value(self, mocker):
        """Test that retry treats any truthy value as success."""
        script = mocker.Mock(side_effect=[None, 0, "", "truthy"])
        policy = Linear(times=5, delay=0)

        result = retry(script, policy=policy)

        assert result == "truthy"
        assert script.call_count == 4

    def test_default_policy(self, mocker):
        """Test that retry uses Linear() policy by default."""
        script = mocker.Mock(side_effect=[False, "success"])

        result = retry(script)

        assert result == "success"
        assert script.call_count == 2

    def test_retry_waits_between_attempts(self, mocker):
        """Test that retry waits the correct amount between attempts."""
        mock_sleep = mocker.patch("toolbox.retries.sleep")

        script = mocker.Mock(side_effect=[False, False, "success"])
        policy = Linear(times=3, delay=0.5)

        result = retry(script, policy=policy)

        assert result == "success"
        # should have slept twice (after first and second failures)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_has_calls([mocker.call(0.5), mocker.call(0.5)])

    def test_no_wait_on_immediate_success(self, mocker):
        """Test that retry doesn't sleep if script succeeds immediately."""
        mock_sleep = mocker.patch("toolbox.retries.sleep")

        script = mocker.Mock(return_value="success")
        policy = Linear(times=3, delay=1.0)

        result = retry(script, policy=policy)

        assert result == "success"
        mock_sleep.assert_not_called()

    def test_varying_delays(self, mocker):
        """Test retry with a custom policy that has varying delays."""
        mock_sleep = mocker.patch("toolbox.retries.sleep")

        # create a custom policy with varying delays
        class CustomPolicy(RetryPolicy):
            def waits(self):
                yield from range(3)

        script = mocker.Mock(side_effect=[False, False, False, "success"])
        policy = CustomPolicy()

        result = retry(script, policy=policy)

        assert result == "success"
        assert mock_sleep.call_count == 3
        mock_sleep.assert_has_calls([mocker.call(delay) for delay in range(3)])
