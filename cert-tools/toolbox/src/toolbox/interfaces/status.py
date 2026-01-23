"""Interface for checking systemd system status."""

from functools import partial
import logging
from typing import Iterable

from toolbox.interfaces import DeviceInterface
from toolbox.devices import ExecutionError
from toolbox.results import BooleanResult
from toolbox.retries import retry, RetryPolicy

logger = logging.getLogger(__name__)


class SystemStatusInterface(DeviceInterface):
    """Provides systemd system status checking capabilities."""

    def get_status(self, allowed: Iterable[str] | None = None) -> BooleanResult:
        """Check if system status is in the allowed set (defaults to 'running')."""
        try:
            result = self.device.run(
                command=["systemctl", "is-system-running"], hide=True
            )
        except ExecutionError as error:
            logger.info(
                "Error retrieving status from %s: %s", self.device.host, str(error)
            )
            return BooleanResult(False)
        status = result.stdout.strip()
        if not status:
            logger.info("No status retrieved from %s", self.device.host)
            return BooleanResult(False)
        allowed = {"running"}.union(allowed or set())
        logger.info(
            "Checking status of %s: %s (allowed: %s)",
            self.device.host,
            status,
            ", ".join(allowed),
        )
        return BooleanResult(status in allowed, message=status)

    def wait_for_status(
        self, allowed: Iterable[str] | None = None, policy: RetryPolicy | None = None
    ) -> BooleanResult:
        """Wait for system status to reach an allowed state, retrying with the given policy."""
        get_status_with_allowed = partial(self.get_status, allowed=allowed)
        get_status_with_allowed.__name__ = self.get_status.__name__
        return retry(get_status_with_allowed, policy=policy)
