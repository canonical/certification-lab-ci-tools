"""Lab device with SSH configuration from environment variables."""

import logging
import os
from typing import Iterable

from fabric.config import Config
from paramiko.config import SSHConfig

from toolbox.devices import RemoteHost
from toolbox.interfaces import DeviceInterface


logger = logging.getLogger(__name__)


class LabExecutionError(RuntimeError):
    pass


class LabDevice(RemoteHost):
    """Remote lab device configured through DEVICE_IP and DEVICE_USER."""

    ssh_options = [
        "StrictHostKeyChecking=no",
        "UserKnownHostsFile=/dev/null",
        "ConnectTimeout=10",
        "ConnectionAttempts=3",
        "ServerAliveInterval=30",
        "ServerAliveCountMax=3",
    ]

    def __init__(
        self,
        host: str | None = None,
        user: str | None = None,
        password: str | None = None,
        interfaces: Iterable[DeviceInterface] | None = None,
    ):
        if not (host := host or os.environ.get("DEVICE_IP")):
            raise LabExecutionError("Host is unspecified and 'DEVICE_IP' is not set")

        super().__init__(
            host=host,
            user=user or os.environ.get("DEVICE_USER", "ubuntu"),
            password=password or os.environ.get("DEVICE_PWD"),
            config=self.create_config(),
            interfaces=interfaces,
        )

    @classmethod
    def create_config(cls):
        """Create SSH config with the lab-specific SSH options."""
        return Config(ssh_config=SSHConfig.from_text("\n".join(cls.ssh_options)))
