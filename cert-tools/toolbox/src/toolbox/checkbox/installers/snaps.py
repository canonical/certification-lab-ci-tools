"""
# get the store token from the device, if available
export STORE=$(_run "snap model --assertion" | sed -n 's/^store:\s\(.*\)$/\1/p')

# use the frontend to derive the Checkbox runtime to be installed
export RUNTIME_NAME=$(get_runtime $FRONTEND_NAME $FRONTEND_TRACK $RISK)
[ "$?" -ne 0 ] && exit 1
RUNTIME_CHANNEL="latest/$RISK"
"""

import logging
import os

from snapstore.client import SnapstoreClient
from toolbox.checkbox.installers import CheckboxInstaller
from toolbox.checkbox.helpers.runtime import CheckboxRuntimeHelper
from toolbox.checkbox.helpers.connector import SnapConnector, Predicate, SelectSnaps
from toolbox.entities.snaps import SnapSpecifier
from toolbox.devices import Device
from toolbox.interfaces.snapd import SnapdAPIClient
from toolbox.interfaces.snaps import SnapInterface, SnapInstallError
from toolbox.retries import Linear


logger = logging.getLogger(__name__)


TOKEN_ENVIRONMENT_VARIABLE = "UBUNTU_STORE_AUTH"


class CheckboxSnapsInstaller(CheckboxInstaller):
    def __init__(
        self,
        device: Device,
        agent: Device,
        frontends: list[SnapSpecifier],
        snapstore: SnapstoreClient,
        predicates: list[Predicate] | None = None,
    ):
        self.device = device
        self.agent = agent
        self.frontends = frontends
        # use store and arch from model or system info to determine runtime
        system = self.device.interfaces[SnapdAPIClient].get("system-info")
        model = self.device.interfaces[SnapdAPIClient].get("model")[0]
        self.store = model.get("store") or system.get("store")
        runtime_helper = CheckboxRuntimeHelper(self.device, snapstore)
        self.runtime = runtime_helper.determine_checkbox_runtime(
            snap=frontends[0], arch=system["architecture"], store=self.store
        )
        self.connector = SnapConnector(
            predicates=(
                [SelectSnaps(frontend.name for frontend in self.frontends)]
                + (predicates if predicates else [])
            )
        )

    @property
    def checkbox_cli(self):
        return f"{self.frontends[0].name}.checkbox-cli"

    def install_frontend_snap(self, snap: SnapSpecifier):
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

    def install_runtime(self):
        logger.info(
            "Installing Checkbox runtime snap: %s from %s",
            self.runtime.name,
            self.runtime.channel,
        )
        self.device.interfaces[SnapInterface].install(
            self.runtime.name, self.runtime.channel, policy=Linear(times=30, delay=10)
        )

    def install_frontends(self):
        # install secondary frontends
        for frontend in self.frontends[1:]:
            self.install_frontend_snap(frontend)
            self.device.run(["sudo", "snap", "stop", "--disable", frontend.name])
        # install primary frontend
        frontend = self.frontends[0]
        self.install_frontend_snap(frontend)
        self.device.run(["sudo", "snap", "set", frontend.name, "agent=enabled"])
        self.device.run(["sudo", "snap", "set", frontend.name, "slave=enabled"])

    def perform_connections(self):
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
            policy=Linear(times=30, delay=10),
        )
        frontend = self.frontends[0]
        logger.info("Restarting primary frontend snap: %s", frontend.name)
        self.device.run(["sudo", "snap", "restart", frontend.name])

    def install_on_device(self):
        self.install_runtime()
        self.install_frontends()
        self.perform_connections()
        self.restart()
