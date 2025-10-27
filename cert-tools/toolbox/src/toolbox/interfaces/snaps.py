"""Interface for managing snap packages on devices."""

from functools import partial
import logging

from toolbox.interfaces import DeviceInterface
from toolbox.interfaces.reboot import RebootInterface
from toolbox.interfaces.snapd import SnapdAPIClient, SnapdAPIError
from toolbox.interfaces.status import SystemStatusInterface
from toolbox.results import BooleanResult
from toolbox.retries import retry, RetryPolicy


logger = logging.getLogger(__name__)


class SnapInterfaceError(RuntimeError):
    pass


class SnapInstallError(SnapInterfaceError):
    pass


class SnapNotFoundError(SnapInstallError):
    pass


class SnapInterface(
    DeviceInterface,
    requires=(RebootInterface, SnapdAPIClient, SystemStatusInterface),
):
    """Provides snap package management capabilities."""

    def get_active(self, snap: str | None = None) -> dict:
        """Get active snap(s) from the device."""
        params = {"snaps": [snap]} if snap else None
        return self.device.interfaces[SnapdAPIClient].get(
            endpoint="snaps", params=params
        )

    def get_changes(self) -> dict:
        """Get all snap changes from the device."""
        return self.device.interfaces[SnapdAPIClient].get(
            endpoint="changes", params={"select": "all"}
        )

    def get_change(self, id: str) -> dict:
        """Get a specific snap change by ID."""
        return self.device.interfaces[SnapdAPIClient].get(endpoint=f"changes/{id}")

    def check_snap_changes_complete(self) -> BooleanResult:
        """Check if all snap changes are in a "ready" state."""
        try:
            changes = self.get_changes()
        except SnapdAPIError as error:
            return BooleanResult(False, str(error))
        complete = all(change["ready"] for change in changes)
        if complete:
            logger.info("No snap operations are ongoing")
            return BooleanResult(True)
        logger.info("Snap operations are ongoing")
        ongoing_changes = [change for change in changes if not change["ready"]]
        for change in ongoing_changes:
            print(f"{change['id']} {change['status']}: {change['summary']}")
        return BooleanResult(
            False,
            "Changes: " + ", ".join(sorted(change["id"] for change in ongoing_changes)),
        )

    def check_snap_changes_complete_and_reboot(
        self, status_policy: RetryPolicy | None = None
    ) -> BooleanResult:
        """Check if snap changes are in a "ready" state, rebooting if needed."""
        complete = self.check_snap_changes_complete()
        if (
            not complete
            and self.device.interfaces[RebootInterface].is_reboot_required()
        ):
            logger.info("Manually rebooting to complete waiting snap changes...")
            self.device.interfaces[RebootInterface].reboot()
            self.device.interfaces[SystemStatusInterface].wait_for_status(
                allowed={"degraded"}, policy=status_policy
            )
            complete = self.check_snap_changes_complete()
        return complete

    def wait_for_snap_changes(
        self,
        policy: RetryPolicy | None = None,
        status_policy: RetryPolicy | None = None,
    ) -> BooleanResult:
        """Wait for snap changes to complete, retrying with the given policy."""
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
    ) -> None:
        """Install or refresh a snap package.

        The action is always performed asynchronously (i.e. with the
        `--no-wait` flag), followed by a wait for all snap changes to
        reach the "ready" state. This is because the action itself or
        an auto-refresh in the background may cause the device to reboot,
        and this approach protects against that.
        """
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
            return
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
