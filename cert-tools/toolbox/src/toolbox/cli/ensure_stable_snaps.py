from argparse import ArgumentParser

from toolbox.devices.lab import LabDevice
from toolbox.interfaces.reboot import RebootInterface
from toolbox.interfaces.snapd import SnapdAPIClient
from toolbox.interfaces.snaps import SnapInstallError, SnapInterface
from toolbox.interfaces.status import SystemStatusInterface
from toolbox.retries import Linear

MAX_RETRY = 3


def main():
    parser = ArgumentParser(
        description="Refresh all installed snaps on a lab device to stable.",
        epilog=(
            "This script uses the DEVICE_IP and DEVICE_USER environment "
            "variables to connect to the lab device."
        ),
    )
    parser.parse_args()

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

    retries = {snap.name: MAX_RETRY for snap in refresh_failed}
    while refresh_failed:
        to_refresh = refresh_failed.pop(0)
        print(f"Retrying to refresh snap: {to_refresh.name}")
        try:
            ld.interfaces[SnapInterface].install(
                to_refresh.name,
                to_refresh.channel,
                refresh_ok=True,
                policy=Linear(times=3, delay=600),
            )
        except SnapInstallError:
            print(f"Failed to refresh snap: {to_refresh.name}")
            refresh_failed.append(to_refresh)
            retries[to_refresh.name] -= 1
            if retries[to_refresh.name] == 0:
                break
    if refresh_failed:
        raise SystemExit(
            "Failed to refresh to stable the following snaps:\n-"
            + "\n-".join(snap.name for snap in refresh_failed)
        )


if __name__ == "__main__":
    main()
