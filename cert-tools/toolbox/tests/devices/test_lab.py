"""Tests for LabDevice."""

import os

import pytest
from fabric.config import Config

from toolbox.devices.lab import LabDevice, LabExecutionError


class TestLabDeviceInitialization:
    """Tests for LabDevice initialization."""

    @pytest.mark.parametrize(
        "env_vars,init_args,expected_host,expected_user",
        [
            # Explicit host and user, no environment variables
            ({}, {"host": "192.168.1.100"}, "192.168.1.100", "ubuntu"),
            (
                {},
                {"host": "192.168.1.100", "user": "testuser"},
                "192.168.1.100",
                "testuser",
            ),
            # Environment variables only
            ({"DEVICE_IP": "10.0.0.50"}, {}, "10.0.0.50", "ubuntu"),
            (
                {"DEVICE_IP": "10.0.0.50", "DEVICE_USER": "labuser"},
                {},
                "10.0.0.50",
                "labuser",
            ),
            # Explicit parameters override environment variables
            (
                {"DEVICE_IP": "10.0.0.50"},
                {"host": "192.168.1.100"},
                "192.168.1.100",
                "ubuntu",
            ),
            (
                {"DEVICE_IP": "10.0.0.50", "DEVICE_USER": "labuser"},
                {"user": "override"},
                "10.0.0.50",
                "override",
            ),
            (
                {"DEVICE_IP": "10.0.0.50", "DEVICE_USER": "labuser"},
                {"host": "192.168.1.100", "user": "override"},
                "192.168.1.100",
                "override",
            ),
        ],
    )
    def test_init_with_host_and_user_combinations(
        self, mocker, env_vars, init_args, expected_host, expected_user
    ):
        """Test LabDevice initialization with various combinations of env vars and args."""
        mocker.patch.dict(os.environ, env_vars, clear=True)
        device = LabDevice(**init_args)
        assert device.host == expected_host
        assert device.user == expected_user

    def test_init_creates_ssh_config(self, mocker):
        """Test that LabDevice initialization creates proper SSH config."""
        mocker.patch.dict(os.environ, {"DEVICE_IP": "10.0.0.50"}, clear=True)
        device = LabDevice()
        assert isinstance(device.config, Config)

    def test_init_without_host_raises_error(self, mocker):
        """Test that missing host and DEVICE_IP raises LabExecutionError."""
        mocker.patch.dict(os.environ, {}, clear=True)
        with pytest.raises(LabExecutionError) as exc_info:
            LabDevice()
        assert "Host is unspecified and 'DEVICE_IP' is not set" in str(exc_info.value)
