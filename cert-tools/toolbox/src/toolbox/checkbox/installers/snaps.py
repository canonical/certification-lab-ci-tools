"""Checkbox installer for snap-based installations."""

import contextlib
import logging
import os

from snapstore.client import SnapstoreClient

from toolbox.checkbox.helpers.connector import Predicate, SelectSnaps, SnapConnector
from toolbox.checkbox.helpers.runtime import CheckboxRuntimeHelper
from toolbox.checkbox.installers import CheckboxInstaller
from toolbox.devices import Device
from toolbox.entities.snaps import SnapSpecifier
from toolbox.interfaces.snapd import SnapdAPIClient
from toolbox.interfaces.snaps import SnapInstallError, SnapInterface
from toolbox.retries import Linear

logger = logging.getLogger(__name__)


TOKEN_ENVIRONMENT_VARIABLE = "UBUNTU_STORE_AUTH"


class CheckboxSnapsInstaller(CheckboxInstaller):
    """Installer for Checkbox frontend and runtime snaps on a device."""

    def __init__(
        self,
        device: Device,
        agent: Device,
        frontends: list[SnapSpecifier],
        snapstore: SnapstoreClient,
        predicates: list[Predicate] | None = None,
    ):
        super().__init__(device=device, agent=agent)
        self.frontends = frontends
        # use store and arch from model or system info to determine runtime
        system = self.device.interfaces[SnapdAPIClient].get("system-info")
        model = self.device.interfaces[SnapdAPIClient].get("model")[0]
        self.store = model.get("store") or system.get("store")
        runtime_helper = CheckboxRuntimeHelper(self.device, snapstore)
        self.runtime = runtime_helper.determine_checkbox_runtime(
            snap=frontends[0], arch=system["architecture"], store=self.store
        )
        selected_snaps = [frontend.name for frontend in self.frontends] + [
            self.runtime.name
        ]
        self.connector = SnapConnector(
            predicates=(
                [SelectSnaps(selected_snaps)] + (predicates if predicates else [])
            )
        )

    @property
    def checkbox_cli(self):
        """Return the command to invoke the Checkbox CLI from the primary frontend snap."""
        return f"{self.frontends[0].name}.checkbox-cli"

    def install_frontend_snap(self, snap: SnapSpecifier):
        """Download and install a Checkbox frontend snap, trying devmode first then classic."""
        env = {
            variable: value
            for variable, value in {
                "UBUNTU_STORE_ID": self.store,
                "UBUNTU_STORE_AUTH": os.environ.get(TOKEN_ENVIRONMENT_VARIABLE),
            }.items()
            if value is not None
        }
        self.device.run(
            [
                "snap",
                "download",
                snap.name,
                f"--channel={snap.channel}",
                f"--basename={snap.name}",
            ],
            env=env,
        )
        self.device.run(["sudo", "snap", "ack", f"{snap.name}.assert"])
        try:
            logger.info(
                "Installing frontend snap '%s' from %s "
                "(as a strict snap, using --devmode)",
                snap.name,
                snap.channel,
            )
            self.device.interfaces[SnapInterface].install(
                f"{snap.name}.snap",
                snap.channel,
                options=["--devmode"],
                policy=Linear(times=30, delay=10),
            )
            strict = True
        except SnapInstallError:
            logger.info(
                "Failed to install '%s' as a strict snap, trying again "
                "(as a classic snap, using --classic)",
                snap.name,
            )
            self.device.interfaces[SnapInterface].install(
                f"{snap.name}.snap",
                snap.channel,
                options=["--classic"],
                policy=Linear(times=30, delay=10),
            )
            strict = False
        return strict

    def custom_frontend_interface(self) -> bool:
        """
        Check if ALL frontends have the custom-frontend interface connected.
        """
        snap_connection_data = self.device.interfaces[SnapdAPIClient].get(
            "connections", params={"select": "all"}
        )

        frontends = {f.name for f in self.frontends}
        for plug in snap_connection_data.get("plugs", []):
            if (
                plug["snap"] == self.runtime.name
                and plug["interface"] == "content"
                and plug.get("attrs", {}).get("content") == "custom-frontend"
            ):
                custom_frontend_plug = plug
                break
        else:
            logger.warning("Installed runtime doesn't provide a custom-frontend plug")
            return False

        for conn in custom_frontend_plug.get("connections", []):
            with contextlib.suppress(KeyError):
                frontends.remove(conn["snap"])

        if frontends:
            return False

        return True

    def configure_agent(self, agent: SnapSpecifier):
        """Configure checkbox snap agent."""
        logger.info("Configuring legacy agent: %s", agent.name)
        self.device.run(["sudo", "snap", "set", agent.name, "agent=enabled"])
        self.device.run(["sudo", "snap", "set", agent.name, "slave=enabled"])
        self.device.run(["sudo", "snap", "start", "--enable", agent.name])

    def install_runtime(self):
        """Install the appropriate Checkbox runtime snap for the frontend."""
        logger.info(
            "Installing Checkbox runtime snap: %s from %s",
            self.runtime.name,
            self.runtime.channel,
        )
        self.device.interfaces[SnapInterface].install(
            self.runtime.name,
            self.runtime.channel,
            options=["--devmode"],
            policy=Linear(times=60, delay=10),
        )

    def install_frontends(self):
        """Install all frontend snaps."""
        for frontend in self.frontends:
            self.install_frontend_snap(frontend)
            self.device.run(["sudo", "snap", "stop", "--disable", frontend.name])

    def perform_connections(self):
        """Automatically connect snap interfaces for the installed Checkbox snaps."""
        snap_connection_data = self.device.interfaces[SnapdAPIClient].get(
            "connections", params={"select": "all"}
        )
        connections, messages = self.connector.process(snap_connection_data)
        for connection in sorted(connections):
            logger.info("Connecting %s", connection)
            self.device.run(
                [
                    "sudo",
                    "snap",
                    "connect",
                    f"{connection.plug_snap}:{connection.plug_name}",
                    f"{connection.slot_snap}:{connection.slot_name}",
                ]
            )
        for message in messages:
            logger.info(message)

    def restart(self):
        # some versions of snapd seem to force dependencies to be stable in some situation
        # but we want a specific risk, so lets force it by re-installing it
        # Note: this is done twice because if snapd doesn't force the stable dependency
        #       then this causes just 1 download
        logger.info("Refreshing runtime snap: %s", self.runtime.name)
        self.device.interfaces[SnapInterface].install(
            self.runtime.name,
            self.runtime.channel,
            options=["--devmode"],
            policy=Linear(times=30, delay=10),
        )

        if self.custom_frontend_interface():
            logger.info("Using new providers interface with runtime agent")
            agent = self.runtime
        else:
            logger.info("Using legacy interface with frontend agent")
            agent = self.frontends[0]

        self.configure_agent(agent)

    def install_on_device(self):
        self.install_runtime()
        self.install_frontends()
        self.perform_connections()
        self.restart()
