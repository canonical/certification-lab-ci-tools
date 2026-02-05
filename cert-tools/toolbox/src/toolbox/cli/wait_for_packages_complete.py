from argparse import ArgumentParser
import sys

from toolbox.devices.lab import LabDevice
from toolbox.retries import Linear
from toolbox.interfaces.debs import DebInterface


def main():
    parser = ArgumentParser(description="Wait until deb operations are complete")
    parser.add_argument("--times", type=int, default=20, help="Number of tries")
    parser.add_argument("--delay", type=int, default=10, help="Delay between retries")
    args = parser.parse_args()

    device = LabDevice(interfaces=[DebInterface()])
    result = device.interfaces[DebInterface].wait_for_complete(
        policy=Linear(times=args.times - 1, delay=args.delay)
    )
    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
