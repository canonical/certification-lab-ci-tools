"""Checkbox installer for deb-based installations."""

import logging

from toolbox.checkbox.installers import CheckboxInstaller, CheckboxInstallerError
from toolbox.devices import Device
from toolbox.entities.risk import Risk
from toolbox.interfaces.debs import DebInterface


logger = logging.getLogger(__name__)


class CheckboxDebsInstaller(CheckboxInstaller):
    """Installer for Checkbox packages on a device."""

    requirements = [
        "fswebcam",
        "fwts",
        "gir1.2-clutter-1.0",
        "iperf",
        "mesa-utils",
        "obexftp",
        "pastebinit",
        "vim",
        "wmctrl",
        "xorg-dev",
    ]

    required_providers = [
        "checkbox-ng",
        "checkbox-provider-base",
        "checkbox-provider-resource",
        "checkbox-provider-sru",
        "python3-checkbox-ng",
    ]

    repositories = [
        "ppa:colin-king/ppa",
        "ppa:colin-king/stress-ng",
        "ppa:firmware-testing-team/ppa-fwts-stable",
    ]

    def __init__(
        self,
        device: Device,
        agent: Device,
        risk: Risk,
        providers: list[str] | None = None,
    ):
        super().__init__(device=device, agent=agent)
        self.risk = risk
        self.additional_providers = providers or []

    @property
    def checkbox_cli(self):
        """Return the command to invoke the Checkbox CLI."""
        return "checkbox-cli"

    def add_repositories(self):
        repositories = self.repositories + [f"ppa:checkbox-dev/{self.risk}"]
        for repository in repositories:
            result = self.device.interfaces[DebInterface].add_repository(repository)
            if not result:
                raise CheckboxInstallerError(
                    f"Failed to add {repository}: {result.message}"
                )

    def install_on_device(self):
        self.device.interfaces[DebInterface].wait_for_complete()
        self.add_repositories()
        self.device.interfaces[DebInterface].install(
            self.requirements + self.required_providers + self.additional_providers
        )
        self.device.interfaces[DebInterface].wait_for_complete()
