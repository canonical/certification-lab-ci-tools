"""Retry mechanisms with configurable policies."""

from abc import ABC, abstractmethod
from itertools import repeat
import logging
from time import sleep
from typing import Any, Callable


logger = logging.getLogger(__name__)


class RetryPolicy(ABC):
    """Abstract base class for retry policies."""

    @abstractmethod
    def waits(self):
        """Generate wait times between retries."""
        raise NotImplementedError


class Linear(RetryPolicy):
    """Retry policy with constant delay between attempts."""

    def __init__(self, times: int | None = None, delay: float = 0):
        self.times = times
        self.delay = delay

    def waits(self):
        """Generate constant wait times, optionally limited by retry count."""
        if self.times is None:
            yield from repeat(self.delay)
        else:
            yield from repeat(self.delay, times=self.times)


def retry(script: Callable, policy: RetryPolicy | None = None) -> Any:
    """Execute script with retries until it returns a truthy value."""
    if not policy:
        policy = Linear()

    result = script()
    if result:
        return result

    for wait in policy.waits():
        logger.info(
            "%s returned %s, retrying%s",
            script.__name__,
            result,
            f" in {wait} seconds" if wait else "",
        )
        sleep(wait)
        result = script()
        if result:
            logger.info("%s returned %s", script.__name__, result)
            return result

    logger.error("Unable to complete '%s'", script.__name__)
    return result
