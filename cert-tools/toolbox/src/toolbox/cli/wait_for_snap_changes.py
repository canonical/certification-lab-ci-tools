from argparse import ArgumentParser
import sys

from toolbox.devices.lab import LabDevice
from toolbox.interfaces.reboot import RebootInterface
from toolbox.interfaces.snaps import SnapInterface
from toolbox.interfaces.snapd import SnapdAPIClient
from toolbox.interfaces.status import SystemStatusInterface
from toolbox.retries import Linear


def main():
    parser = ArgumentParser(description="Wait until all snap changes are complete")
    parser.add_argument("--times", type=int, default=180, help="Number of tries")
    parser.add_argument("--delay", type=int, default=30, help="Delay between retries")
    args = parser.parse_args()

    device = LabDevice(
        interfaces=[
            SystemStatusInterface(),
            RebootInterface(),
            SnapdAPIClient(),
            SnapInterface(),
        ]
    )
    result = device.interfaces[SnapInterface].wait_for_snap_changes(
        policy=Linear(times=args.times - 1, delay=args.delay),
        status_policy=Linear(delay=10),
    )
    sys.exit(1 - int(result))


if __name__ == "__main__":
    main()
