import logging
from functools import partial
from typing import Iterable, NamedTuple

from toolbox.interfaces import DeviceInterface
from toolbox.devices import ExecutionError
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
    def get_status(self, allowed: Iterable[str] | None = None) -> SystemStatus:
        try:
            result = self.device.run(
                command=["systemctl", "is-system-running"], hide=True
            )
        except ExecutionError as error:
            logger.error(error)
            return SystemStatus(exited=255)
        status = result.stdout.strip()
        if not status:
            logger.info(
                "Unable to retrieve status from '%s'",
                self.device.host,
            )
            return SystemStatus(result.exited)
        allowed = {"running"}.union(allowed or set())
        allowed_message = ", ".join(allowed)
        logger.info(
            "Checking status of '%s': %s (allowed: %s)",
            self.device.host,
            status,
            allowed_message,
        )
        return SystemStatus(
            exited=0 if status in allowed else result.exited, status=status
        )

    def wait_for_status(
        self, allowed: Iterable[str] | None = None, policy: RetryPolicy | None = None
    ) -> SystemStatus:
        get_status_with_allowed = partial(self.get_status, allowed=allowed)
        get_status_with_allowed.__name__ = self.get_status.__name__
        return retry(get_status_with_allowed, policy=policy)
