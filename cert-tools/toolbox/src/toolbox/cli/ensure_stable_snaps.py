from contextlib import suppress

from toolbox.devices.lab import LabDevice
from toolbox.interfaces.reboot import RebootInterface
from toolbox.interfaces.snapd import SnapdAPIClient
from toolbox.interfaces.snaps import SnapInstallError, SnapInterface
from toolbox.interfaces.status import SystemStatusInterface
from toolbox.retries import Linear

MAX_RETRY = 3


def main():
    ld = LabDevice(
        interfaces=[
            SystemStatusInterface(),
            RebootInterface(),
            SnapdAPIClient(),
            SnapInterface(),
        ]
    )
    print("Refreshing all installed snaps to stable")
    installed_snaps = ld.interfaces[SnapInterface].list()
    refresh_failed = []
    for snap in installed_snaps:
        snap.risk = "stable"
        # ingore refresh errors as there may be dependencies between refreshes
        # that aren't trivial to fix right away, for now refresh as much as we
        # can
        try:
            print(f"Refreshing '{snap.name}' to '{snap.channel}'")
            ld.interfaces[SnapInterface].install(
                snap.name,
                snap.channel,
                refresh_ok=True,
                policy=Linear(times=3, delay=60),
            )
        except SnapInstallError:
            refresh_failed.append(snap)
            print(f"Snap '{snap.name}' failed to refresh, retrying at the end")

    retry = MAX_RETRY
    while refresh_failed and retry > 0:
        to_refresh = refresh_failed.pop(0)
        print("Retrying to refresh snap: {to_refresh.name}")
        try:
            ld.interfaces[SnapInterface].install(
                to_refresh.name,
                to_refresh.channel,
                refresh_ok=True,
                policy=Linear(times=3, delay=600),
            )
            retry = MAX_RETRY
        except SnapInstallError:
            print("Failed to refresh snap: {to_refresh.name}")
            refresh_failed.append(snap)
            retry -= 1


if __name__ == "__main__":
    main()
