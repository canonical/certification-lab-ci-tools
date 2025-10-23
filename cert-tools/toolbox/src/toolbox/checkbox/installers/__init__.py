"""Base classes for Checkbox installation on devices."""

from abc import ABC, abstractmethod
import logging


from toolbox.checkbox.helpers.github import CheckboxVersionHelper
from toolbox.devices import Device


logger = logging.getLogger(__name__)


class CheckboxInstallerError(Exception):
    pass


class CheckboxInstaller(ABC):
    """Abstract base class for installing Checkbox on a device and agent."""

    def __init__(self, device: Device, agent: Device):
        self.device = device
        self.agent = agent

    @property
    @abstractmethod
    def checkbox_cli(self, *args, **kwargs) -> str:
        """Return the command to invoke the Checkbox CLI on the device."""
        raise NotImplementedError

    def check_service(self):
        """Check that the Checkbox service is active on the device."""
        logger.info(
            "Checking if the Checkbox service is active on %s", self.device.host
        )
        result = self.device.run(["systemctl", "is-active", "*checkbox*.service"])
        if not result or result.stdout.strip() != "active":
            raise CheckboxInstallerError(
                f"Checkbox service is not active on {self.device.host}"
            )

    def get_version(self) -> str:
        """Get the Checkbox version installed on the device."""
        result = self.device.run([self.checkbox_cli, "--version"])
        if not result:
            raise CheckboxInstallerError(
                f"Unable to retrieve Checkbox version from {self.device.host}"
            )
        return result.stdout.strip()

    def install_from_source_on_agent(self, version: str):
        """Install matching Checkbox version from source on the agent using pipx."""
        logger.info(
            "Installing Checkbox %s on the agent container from source", version
        )
        commit = CheckboxVersionHelper().get_commit_for_version(version)
        self.agent.run(
            [
                "pipx",
                "install",
                f"git+https://github.com/canonical/checkbox.git@{commit}#subdirectory=checkbox-ng",
                "--force",
            ]
        )

    @abstractmethod
    def install_on_device(self, *args, **kwargs):
        """Install Checkbox on the device."""
        raise NotImplementedError

    def install(self, *args, **kwargs):
        """Install Checkbox on both device and agent, ensuring versions match."""
        self.install_on_device(*args, **kwargs)
        self.check_service()
        version = self.get_version()
        self.install_from_source_on_agent(version)
