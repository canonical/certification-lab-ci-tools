from abc import ABC, abstractmethod
import logging


from toolbox.checkbox.helpers.github import CheckboxVersionHelper
from toolbox.devices import Device


logger = logging.getLogger(__name__)


class CheckboxInstallerError(Exception):
    pass


"""
from toolbox.devices.lab import LabDevice
from toolbox.interfaces.snapd import SnapdAPIClient
from toolbox.interfaces.snaps import SnapInterface
from toolbox.interfaces.reboot import RebootInterface
from toolbox.interfaces.status import SystemStatusInterface
device = LabDevice(interfaces=[RebootInterface(), SnapdAPIClient(), SnapInterface(), SystemStatusInterface()])
from snapstore.client import SnapstoreClient
from snapstore.craft import create_base_client
from toolbox.checkbox.installer.snaps import TOKEN_ENVIRONMENT_VARIABLE
client = SnapstoreClient(create_base_client(TOKEN_ENVIRONMENT_VARIABLE)
from toolbox.entities.channels import Channel
from toolbox.entities.snaps import SnapSpecifier
from toolbox.checkbox.installer import CheckboxInstaller, TOKEN_ENVIRONMENT_VARIABLE
installer = CheckboxInstaller(device, info)
# installer.install(frontends=[SnapSpecifier("checkbox", Channel.from_string("latest/beta"))])
installer.install(frontends=[SnapSpecifier("checkbox", Channel.from_string("uc24/beta"))])
"""


class CheckboxInstaller(ABC):
    def __init__(self, device: Device, agent: Device):
        self.device = device
        self.agent = agent

    @property
    @abstractmethod
    def checkbox_cli(self, *args, **kwargs) -> str:
        raise NotImplementedError

    def check_service(self):
        logger.info(
            "Checking if the Checkbox service is active on %s", self.device.host
        )
        result = self.device.run(["systemctl", "is-active", "*checkbox*.service"])
        if not result or result.stdout.strip() != "active":
            raise CheckboxInstallerError(
                f"Checkbox service is not active on {self.device.host}"
            )

    def get_version(self) -> str:
        result = self.device.run([self.checkbox_cli, "--version"])
        if not result:
            raise CheckboxInstallerError(
                f"Unable to retrieve Checkbox version from {self.device.host}"
            )
        return result.stdout.strip()

    def install_from_source_on_agent(self, version: str):
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
        raise NotImplementedError

    def install(self, *args, **kwargs):
        self.install_on_device(*args, **kwargs)
        self.check_service()
        version = self.get_version()
        self.install_from_source_on_agent(version)
