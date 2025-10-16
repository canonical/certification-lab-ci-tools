from abc import ABC, abstractmethod
from itertools import repeat
import logging
from time import sleep
from typing import Any, Callable


logger = logging.getLogger(__name__)


class RetryPolicy(ABC):
    @abstractmethod
    def waits(self):
        raise NotImplementedError


class Linear(RetryPolicy):
    def __init__(self, times: int | None = None, delay: float = 0):
        self.times = times
        self.delay = delay

    def waits(self):
        yield from repeat(self.delay, self.times)


def retry(script: Callable, policy: RetryPolicy | None = None) -> Any:
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
