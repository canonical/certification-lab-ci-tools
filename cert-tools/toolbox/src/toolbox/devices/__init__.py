from abc import ABC, abstractmethod
import logging
import shlex
from typing import Iterable

from fabric import Connection
from invoke import Context, Result
from invoke.exceptions import Failure, ThreadException
from paramiko.config import SSHConfig
from paramiko.ssh_exception import SSHException


from toolbox.interfaces import DeviceInterface
from toolbox.devices.registry import DeviceInterfaceRegistry


logger = logging.getLogger(__name__)


CommandType = str | Iterable[str]


class ExecutionError(RuntimeError):
    def __init__(self, command: str, device: "Device", error: Exception):
        super().__init__(f"Failed to run '{command}' on {device}: {error}")


class Device(ABC):
    def __init__(self, host: str, interfaces: Iterable[DeviceInterface] | None = None):
        self.host = host
        self.interfaces = DeviceInterfaceRegistry(interfaces or ())
        for interface in self.interfaces:
            interface.attach_to(self)

    def __str__(self):
        return f"{type(self).__name__}('{self.host}')"

    @staticmethod
    def _process(command: CommandType) -> str:
        if isinstance(command, str):
            return command
        else:
            return shlex.join(command)

    @abstractmethod
    def run(self, command: CommandType, **kwargs) -> Result:
        raise NotImplementedError


class LocalHost(Device):
    def __init__(self, interfaces: Iterable[DeviceInterface] | None = None):
        super().__init__(host="localhost", interfaces=interfaces)

    def run(self, command: CommandType, **kwargs) -> Result:
        command = self._process(command)
        try:
            return Context().run(command, warn=True, **kwargs)
        except (Failure, ThreadException, OSError) as error:
            return Result(exited=255, stderr=str(error))


class RemoteHost(Device):
    def __init__(
        self,
        host: str,
        user: str | None = None,
        config: SSHConfig | None = None,
        interfaces: Iterable[DeviceInterface] | None = None,
    ):
        super().__init__(host=host, interfaces=interfaces)
        self.user = user
        self.config = config

    def create_connection(self) -> Connection:
        return Connection(self.host, user=self.user, config=self.config)

    def run(self, command: CommandType, **kwargs) -> Result:
        command = self._process(command)
        logger.debug(command)
        with self.create_connection() as connection:
            try:
                return connection.run(command, warn=True, **kwargs)
            except (SSHException, Failure, ThreadException, OSError) as error:
                return Result(exited=255, stderr=str(error))
