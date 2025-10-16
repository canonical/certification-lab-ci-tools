from invoke import Result
import logging
from typing import Iterable, NamedTuple

from toolbox.interfaces import DeviceInterface
from toolbox.devices import Device, ExecutionError
# from toolbox.result import ExecutionResult
from toolbox.retries import retry, RetryPolicy


logger = logging.getLogger(__name__)


class SystemStatus(NamedTuple):
    exited: int
    status: str | None = None

    def __str__(self) -> str:
        return self.status or str(self.exited)

    def __bool__(self) -> str:
        return self.exited == 0


class SystemStatusInterface(DeviceInterface):
    def __init__(self, device: Device, allowed: Iterable[str] | None = None):
        self.device = device
        self.allowed = {"running"}.union(allowed or set())
        self.allowed_message = ", ".join(self.allowed)

    def get_status(self) -> SystemStatus:
        try:
            result = self.device.run(
                command=["systemctl", "is-system-running"], hide=True
            )
        except ExecutionError as error:
            logger.error(error)
            return SystemStatus(exited=255)
        status = result.stdout.strip()
        logger.info(
            "Checking status of '%s': %s (allowed: %s)",
            self.device.host,
            status,
            self.allowed_message,
        )
        return SystemStatus(exited=0 if status in self.allowed else result.exited, status=status)

    def wait_for_status(self, policy: RetryPolicy | None = None) -> SystemStatus:
        return retry(self.get_status, policy=policy)
