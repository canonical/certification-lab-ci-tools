import logging
from typing import Iterable

from invoke import Result

# from toolbox.result import ExecutionResult
from toolbox.interfaces import DeviceInterface
from toolbox.retries import retry, RetryPolicy

logger = logging.getLogger(__name__)


class DebInterface(DeviceInterface):
    options = [
        "-o",
        "Dpkg::Options::=--force-confdef",
        "-o",
        "Dpkg::Options::=--force-confold",
    ]

    files = [
        "/var/lib/apt/lists/lock",
        "/var/lib/dpkg/lock",
        "/var/lib/dpkg/lock-frontend",
        "/var/cache/debconf/config.dat",
    ]

    def action(self, action: str, options: Iterable[str] | None = None) -> bool:
        command = (
            ["sudo", "DEBIAN_FRONTEND=noninteractive", "apt-get", "-qqy"]
            + self.options
            + (options or [])
            + [action]
        )
        logger.debug(command)
        result = self.device.run(command)
        return result.exited == 0

    def update(self) -> bool:
        return self.action("update")

    def upgrade(self, options: Iterable[str] | None = None) -> bool:
        return self.action("dist-upgrade", options)

    def install(
        self, packages: Iterable[str], options: Iterable[str] | None = None
    ) -> bool:
        return self.action("install", packages + (options or []))

    def are_package_processes_ongoing(self) -> Result:
        return self.device.run(["pgrep", "--list-full", "^apt|dpkg"], hide=True)

    def are_package_files_open(self) -> Result:
        return self.device.run(["sudo", "fuser"] + self.files, hide=True)

    def check_complete(self):
        processes = self.are_package_processes_ongoing()
        files = self.are_package_files_open()
        complete = not processes and not files
        if not complete:
            logger.info("Package operations are ongoing")
            if processes:
                print(processes.stdout, end="")
            if files:
                # fuser writes diagnostic information to stderr
                print(files.stderr, end="")
        else:
            logger.info("No package operations are ongoing")
        return complete

    def wait_for_complete(self, policy: RetryPolicy | None = None) -> bool:
        return retry(self.check_complete, policy=policy)
