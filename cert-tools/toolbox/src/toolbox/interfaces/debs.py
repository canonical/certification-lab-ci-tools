"""Interface for managing Debian packages on devices."""

import logging
from typing import Iterable

from invoke import Result

from toolbox.results import BooleanResult
from toolbox.interfaces import DeviceInterface
from toolbox.retries import retry, RetryPolicy

logger = logging.getLogger(__name__)


class DebInterface(DeviceInterface):
    """Provides Debian package management capabilities for devices."""

    options = [
        "-o",
        "Dpkg::Options::=--force-confdef",
        "-o",
        "Dpkg::Options::=--force-confold",
    ]

    # to be monitored, suggesting package management operations are ongoing
    files = [
        "/var/lib/apt/lists/lock",
        "/var/lib/dpkg/lock",
        "/var/lib/dpkg/lock-frontend",
        "/var/cache/debconf/config.dat",
    ]

    def action(
        self,
        action: str,
        options: Iterable[str] | None = None,
        action_options: Iterable[str] | None = None,
    ) -> BooleanResult:
        """Execute an apt-get action with the options provided."""
        command = (
            ["sudo", "DEBIAN_FRONTEND=noninteractive", "apt-get", "-qqy"]
            + self.options
            + (options or [])
            + [action]
            + (action_options or [])
        )
        result = self.device.run(command)
        return BooleanResult(bool(result), message=result.stderr)

    def update(self) -> BooleanResult:
        """Run apt-get update."""
        logger.info("Updating")
        return self.action("update")

    def upgrade(self, options: Iterable[str] | None = None) -> BooleanResult:
        """Run apt-get dist-upgrade."""
        logger.info("Upgrading")
        return self.action("dist-upgrade", options=options)

    def install(
        self, packages: Iterable[str], options: Iterable[str] | None = None
    ) -> BooleanResult:
        """Install Debian packages via apt-get."""
        logger.info("Installing packages: %s", ", ".join(packages))
        return self.action("install", options=options, action_options=packages)

    def add_repository(self, repository: str) -> BooleanResult:
        """Run add-apt-repository."""
        logger.info("Adding repository: %s", repository)
        command = [
            "sudo",
            "DEBIAN_FRONTEND=noninteractive",
            "add-apt-repository",
            "-y",
        ] + [repository]
        result = self.device.run(command, hide=True)
        return BooleanResult(bool(result), message=result.stderr)

    def are_package_processes_ongoing(self) -> Result:
        """Check if apt or dpkg processes are running."""
        return self.device.run(["pgrep", "--list-full", "^apt|dpkg"], hide=True)

    def are_package_files_open(self) -> Result:
        """Check if package management lock files are open."""
        return self.device.run(["sudo", "fuser"] + self.files, hide=True)

    def check_complete(self) -> bool:
        """Check if all package operations are complete."""
        processes = self.are_package_processes_ongoing()
        files = self.are_package_files_open()
        complete = not processes and not files
        if not complete:
            logger.info("Package operations are ongoing")
            if processes:
                logger.info(processes.stdout.rstrip())
            if files:
                # fuser writes diagnostic information to stderr
                logger.info(files.stderr.rstrip())
        else:
            logger.info("No package operations are ongoing")
        return complete

    def wait_for_complete(self, policy: RetryPolicy | None = None) -> bool:
        """Wait for package operations to complete, retrying with the given policy."""
        return retry(self.check_complete, policy=policy)
