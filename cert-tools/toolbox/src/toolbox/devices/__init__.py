from abc import ABC, abstractmethod
import logging
import shlex
from typing import Iterable

from fabric import Connection
from invoke import Context, Result
from invoke.exceptions import Failure, ThreadException
from paramiko.config import SSHConfig


logger = logging.getLogger(__name__)


CommandType = str | Iterable[str]


class ExecutionError(RuntimeError):
    def __init__(self, command: str, device: "Device", error: Exception):
        super().__init__(f"Failed to run '{command}' on {device}: {error}")


class Device(ABC):
    def __init__(self, host: str):
        self.host = host

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
    def __init__(self):
        super().__init__(host="localhost")

    def run(self, command: CommandType, **kwargs) -> Result:
        command = self._process(command)
        try:
            return Context().run(command, warn=True, **kwargs)
        except (Failure, ThreadException, OSError) as error:
            raise ExecutionError(command, self, error) from error


class RemoteHost(Device):
    def __init__(
        self, host: str, user: str | None = None, config: SSHConfig | None = None
    ):
        super().__init__(host)
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
            except (Failure, ThreadException, OSError) as error:
                raise ExecutionError(command, self, error) from error
