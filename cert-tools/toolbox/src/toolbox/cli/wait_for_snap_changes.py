from argparse import ArgumentParser, REMAINDER
import logging
import sys

from toolbox.scripts.devices import LabDevice
from toolbox.scripts.direct import wait_for_running
from toolbox.scripts.retries import Linear
from toolbox.scripts.snaps import SnapdAPIClient, SnapManager


logger = logging.Logger(__name__)


def run():
    parser = ArgumentParser(description="Run commands on the device")
    parser.add_argument(
        "command", nargs=REMAINDER, help="Command to run on remote device"
    )
    args = parser.parse_args()

    if not args.command:
        logger.error("No command specified")
        sys.exit(1)

    LabDevice().run(args.command)


def wait_for_ssh_entry_point():
    parser = ArgumentParser(description="Wait until the device is running")
    parser.add_argument(
        "--allow-degraded",
        action="store_true",
        help="Consider 'degraded' an acceptable state",
    )
    parser.add_argument(
        "--allow-starting",
        action="store_true",
        help="Consider 'starting' an acceptable state",
    )
    parser.add_argument("--allow", nargs="+", help="Specify acceptable state(s)")
    parser.add_argument("--times", type=int, default=20, help="Number of tries")
    parser.add_argument("--delay", type=int, default=10, help="Delay between retries")
    args = parser.parse_args()

    allowed = set(args.allow or tuple())
    if args.allow_degraded:
        allowed.add("degraded")
    if args.allow_starting:
        allowed.add("starting")

    wait_for_running(
        device=LabDevice(),
        allowed=allowed,
        policy=Linear(times=args.times, delay=args.delay),
    )


def wait_for_snap_changes_entry_point():
    parser = ArgumentParser(description="Wait until all snap changes are complete")
    parser.add_argument("--times", type=int, default=180, help="Number of tries")
    parser.add_argument("--delay", type=int, default=30, help="Delay between retries")
    args = parser.parse_args()

    device = LabDevice()
    client = SnapdAPIClient(device)
    manager = SnapManager(client)
    manager.wait_for_snap_changes(policy=Linear(times=args.times, delay=args.delay))
