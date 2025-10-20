from functools import partial
import logging

from toolbox.interfaces import DeviceInterface
from toolbox.interfaces.reboot import RebootInterface
from toolbox.interfaces.snapd import SnapdAPIClient
from toolbox.interfaces.status import SystemStatusInterface
from toolbox.retries import retry, RetryPolicy


logger = logging.getLogger(__name__)


class SnapInstallError(RuntimeError):
    pass


class SnapNotFoundError(SnapInstallError):
    pass


class SnapInterface(
    DeviceInterface,
    requires=(RebootInterface, SnapdAPIClient, SystemStatusInterface),
):
    def get_active(self, snap: str | None = None):
        params = {"snaps": [snap]} if snap else None
        return self.device.interfaces[SnapdAPIClient].get(
            endpoint="snaps", params=params
        )

    def get_changes(self):
        return self.device.interfaces[SnapdAPIClient].get(
            endpoint="changes", params={"select": "all"}
        )

    def get_change(self, id: str):
        return self.device.interfaces[SnapdAPIClient].get(endpoint=f"changes/{id}")

    def check_snap_changes_complete(self) -> bool:
        changes = self.get_changes()
        complete = all(change["ready"] for change in changes)
        if complete:
            logger.info("No snap operations are ongoing")
            return True
        logger.info("Snap operations are ongoing")
        for change in changes:
            if not change["ready"]:
                print(f"{change['id']} {change['status']}: {change['summary']}")
        return False

    def check_snap_changes_complete_and_reboot(
        self, status_policy: RetryPolicy | None = None
    ) -> bool:
        complete = self.check_snap_changes_complete()
        if (
            not complete
            and self.device.interfaces[RebootInterface].is_reboot_required()
        ):
            logger.info("Manually rebooting to complete waiting snap changes...")
            self.device.interfaces[RebootInterface].reboot()
            self.device.interfaces[SystemStatusInterface].wait_for_running(
                allowed={"degraded"}, policy=status_policy
            )
            complete = self.check_snap_changes_complete()
        return complete

    def wait_for_snap_changes(
        self,
        policy: RetryPolicy | None = None,
        status_policy: RetryPolicy | None = None,
    ):
        check_snap_changes = partial(
            self.check_snap_changes_complete_and_reboot, status_policy=status_policy
        )
        check_snap_changes.__name__ = (
            self.check_snap_changes_complete_and_reboot.__name__
        )
        return retry(check_snap_changes, policy=policy)

    def install(
        self,
        snap: str,
        channel: str | None = None,
        options: list[str] | None = None,
        refresh_ok: bool = False,
        policy: RetryPolicy | None = None,
    ) -> bool:
        action = "refresh" if self.get_active(snap) and refresh_ok else "install"
        command = ["sudo", "snap", action, "--no-wait", snap]
        if channel:
            command.append(f"--channel={channel}")
        if options:
            command.extend(options)
        install_result = self.device.run(command, hide=True)
        if not install_result:
            error_cls = (
                SnapNotFoundError
                if "not found" in install_result.stderr
                else SnapInstallError
            )
            raise error_cls(f"Failed to run '{command}': {install_result.stderr}")
        snap_change_id = install_result.stdout.strip()
        if not snap_change_id:
            return True
        wait_result = self.wait_for_snap_changes(policy=policy)
        snap_change = self.get_change(snap_change_id)
        if not wait_result:
            raise SnapInstallError(
                f"Snap change {snap_change_id} timed-out: {snap_change['summary']}"
            )
        if not snap_change["status"] == "Done":
            raise SnapInstallError(
                f"Snap change {snap_change_id} incomplete: {snap_change['status']}"
            )


"""
class SnapAction(NamedTuple):
    action: str
    snap: str
    channel: SnapChannel | None = None

    def __str__(self):
        return " ".join(str(component) for component in self if component)


class SnapInstaller:

    def __init__(self, targets: Iterable[SnapDict]):
        self.target_index = self.create_index(targets)

    @staticmethod
    def create_index(snaps: Iterable[SnapDict]):
        return {
            snap["name"]: (
                SnapChannel.from_string(channel)
                if (
                    "channel" in snap and
                    (channel := snap["channel"]) or
                    "tracking-channel" in snap and
                    (channel := snap["tracking-channel"])
                )
                else None
            )
            for snap in snaps
        }

    @staticmethod
    def action(snap: str, target_channel: SnapChannel, active_channel: SnapChannel | None = None):
        if not active_channel:
            return SnapAction("install", snap=snap, channel=target_channel)
        if target_channel != active_channel:
            return SnapAction("refresh", snap=snap, channel=target_channel)
        return SnapAction("refresh", snap=snap)

    def process(self, active: Iterable[SnapDict]):
        active_index = self.create_index(active)
        actions = []
        # iterate over active, untargeted snaps and refresh to stable
        for snap, active_channel in active_index.items():
            if snap not in self.target_index:
                actions.append(
                    self.action(snap, active_channel.stabilize(), active_channel)
                )
        # iterate over targeted staps and install or refresh to target
        for snap, target_channel in self.target_index.items():
            active_channel = active_index.get(snap)
            actions.append(
                self.action(snap, target_channel, active_channel)
            )
        return actions

    installer = SnapInstaller(args.targets)
    actions = installer.process(args.active)
"""
