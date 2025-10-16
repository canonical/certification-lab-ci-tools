from argparse import ArgumentParser
import logging
import sys

from toolbox.devices.lab import LabDevice
from toolbox.retries import Linear
from toolbox.interfaces.status import SystemStatusInterface


logger = logging.Logger(__name__)


def main():
    parser = ArgumentParser(description="Wait until a lab device is running")
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

    device = LabDevice(interfaces=[SystemStatusInterface()])
    result = device.interfaces[SystemStatusInterface].wait_for_status(
        allowed=allowed, policy=Linear(times=args.times - 1, delay=args.delay)
    )
    sys.exit(result.exited)


if __name__ == "__main__":
    main()
