from argparse import ArgumentParser, REMAINDER
import logging
from pathlib import Path
import sys

from toolbox.devices import ExecutionError
from toolbox.devices.lab import LabDevice, LabExecutionError


logger = logging.Logger(__name__)


def main():
    parser = ArgumentParser(description="Run commands on a lab device")
    parser.add_argument(
        "command", nargs=REMAINDER, help="Command to run on remote device"
    )
    args = parser.parse_args()

    if not args.command:
        logger.error("%s: No command specified", Path(sys.argv[0]).name)
        sys.exit(1)

    try:
        result = LabDevice().run(args.command)
    except (ExecutionError, LabExecutionError) as error:
        logger.error(error)
        sys.exit(1)

    sys.exit(result.exited)


if __name__ == "__main__":
    main()
