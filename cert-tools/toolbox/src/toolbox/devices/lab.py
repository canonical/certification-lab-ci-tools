import logging
import os

from fabric.config import Config
from paramiko.config import SSHConfig

from toolbox.devices import RemoteHost


logger = logging.getLogger(__name__)


class LabExecutionError(RuntimeError):
    pass


class LabDevice(RemoteHost):
    ssh_options = [
        "StrictHostKeyChecking=no",
        "UserKnownHostsFile=/dev/null",
        "ConnectTimeout=10",
        "ConnectionAttempts=3",
        "ServerAliveInterval=30",
        "ServerAliveCountMax=3",
    ]

    def __init__(self, host: str | None = None, user: str | None = None):
        if not (host := host or os.environ.get("DEVICE_IP")):
            raise LabExecutionError("Host is unspecified and 'DEVICE_IP' is not set")
        super().__init__(
            host=host,
            user=user or os.environ.get("DEVICE_USER", "ubuntu"),
            config=self.create_config(),
        )

    @classmethod
    def create_config(cls):
        return Config(ssh_config=SSHConfig.from_text("\n".join(cls.ssh_options)))
