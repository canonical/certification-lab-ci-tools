# Tests for the mailtool script
# Run as ``pytest test_mailtool.py``

import sys
import os
import importlib.util
import pytest
import socket
from unittest.mock import patch, MagicMock
from pathlib import Path


def load_mailtool():
    """
    This function explicitely loads the module from the file ``mailtool``
    and not from ``mailtool.py``.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "mailtool")

    from importlib.machinery import SourceFileLoader

    loader = SourceFileLoader("mailtool_mod", file_path)
    spec = importlib.util.spec_from_loader("mailtool_mod", loader)
    module = importlib.util.module_from_spec(spec)

    sys.modules["mailtool_mod"] = module

    spec.loader.exec_module(module)
    return module


mailtool = load_mailtool()


class TestSMTPConnection:
    """
    Tests for the smtp_connect_with_retries function.
    """

    @patch("smtplib.SMTP")
    def test_success_on_first_attempt(self, mock_smtp):
        """
        Verifies that the script succeeds immediately if the network is fine.
        """
        mock_connection = MagicMock()
        mock_smtp.return_value = mock_connection

        result = mailtool.smtp_connect_with_retries(
            retries=3, base_timeout_secs=30, wait_time_secs=5
        )

        assert result == mock_connection
        assert mock_smtp.call_count == 1

    @patch("smtplib.SMTP")
    def test_success_on_second_attempt(self, mock_smtp):
        """
        Verifies that the script stops retrying after a success.
        """
        mock_connection = MagicMock()
        mock_smtp.side_effect = [
            TimeoutError,
            mock_connection,
        ]

        result = mailtool.smtp_connect_with_retries(
            retries=5, base_timeout_secs=1, wait_time_secs=0.1
        )

        # Check that the inner function was only called twice and the tested
        # function returned the connection object
        assert result == mock_connection
        assert mock_smtp.call_count == 2

    @patch("smtplib.SMTP")
    def test_socket_timeout(self, mock_smtp):
        """
        Verifies that the script also works with socket.timeout which gets
        raised by earlier versions of smtplib.
        """
        mock_connection = MagicMock()
        mock_smtp.side_effect = [
            socket.timeout,
            mock_connection,
        ]

        result = mailtool.smtp_connect_with_retries(
            retries=5, base_timeout_secs=1, wait_time_secs=0.1
        )

        # Check that the inner function was only called twice and the tested
        # function returned the connection object
        assert result == mock_connection
        assert mock_smtp.call_count == 2

    @patch("smtplib.SMTP")
    def test_recovery_from_other_errors(self, mock_smtp):
        """
        Verify that the function also retries if an error other than timeout
        occurs.
        """
        mock_connection = MagicMock()
        mock_smtp.side_effect = [
            Exception("Random Network Error"),
            mock_connection,
        ]

        result = mailtool.smtp_connect_with_retries(
            retries=2, base_timeout_secs=1, wait_time_secs=0.1
        )

        assert result == mock_connection
        assert mock_smtp.call_count == 2

    @patch("smtplib.SMTP")
    def test_success_on_final_attempt(self, mock_smtp):
        """
        Verifies that the script succeeds if the last retry works.
        """
        mock_conn = MagicMock()
        # Fail, Fail, then Success
        mock_smtp.side_effect = [TimeoutError, Exception("Refused"), mock_conn]

        result = mailtool.smtp_connect_with_retries(
            retries=3, base_timeout_secs=1, wait_time_secs=0.1
        )

        assert result == mock_conn
        assert mock_smtp.call_count == 3

    @patch("smtplib.SMTP")
    def test_all_fails(self, mock_smtp):
        """
        Verifies what happens when the function fails every time.
        """
        mock_smtp.side_effect = TimeoutError

        result = mailtool.smtp_connect_with_retries(
            retries=3, base_timeout_secs=10, wait_time_secs=0.1
        )

        # All attemps should fail so result is None and the function should be
        # called 3 times
        assert result is None
        assert mock_smtp.call_count == 3

        # Check the timeout values for the function calls
        assert mock_smtp.call_args_list[0][1]["timeout"] == 10
        assert mock_smtp.call_args_list[1][1]["timeout"] == 20
        assert mock_smtp.call_args_list[2][1]["timeout"] == 40
