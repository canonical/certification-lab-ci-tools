from argparse import ArgumentParser
from pathlib import Path

from snapstore.client import SnapstoreClient
from snapstore.craft import create_base_client
from toolbox.checkbox.installers.snaps import (
    CheckboxSnapsInstaller,
    TOKEN_ENVIRONMENT_VARIABLE,
)
from toolbox.devices import LocalHost
from toolbox.devices.lab import LabDevice
from toolbox.checkbox.helpers.connector import Blacklist
from toolbox.entities.snaps import SnapSpecifier
from toolbox.interfaces.reboot import RebootInterface
from toolbox.interfaces.snaps import SnapInterface
from toolbox.interfaces.snapd import SnapdAPIClient
from toolbox.interfaces.status import SystemStatusInterface


def main():
    parser = ArgumentParser(
        description="Install Checkbox on device (from snaps) and agent (from source)"
    )
    parser.add_argument("frontend", help="Checkbox frontend snap")
    parser.add_argument(
        "--additional",
        dest="frontends",
        nargs="+",
        help="Specify additional frontend snap specs",
    )
    parser.add_argument(
        "--blacklist", type=Path, help="Path to the connections blacklist"
    )
    args = parser.parse_args()

    frontends = [SnapSpecifier.from_string(args.frontend)] + [
        SnapSpecifier.from_string(frontend) for frontend in args.frontends or ()
    ]
    device = LabDevice(
        interfaces=[
            SystemStatusInterface(),
            RebootInterface(),
            SnapdAPIClient(),
            SnapInterface(),
        ]
    )
    installer = CheckboxSnapsInstaller(
        device=device,
        agent=LocalHost(),
        frontends=frontends,
        snapstore=SnapstoreClient(create_base_client(TOKEN_ENVIRONMENT_VARIABLE)),
        predicates=[Blacklist.from_file(args.blacklist)] if args.blacklist else None,
    )
    installer.install()


if __name__ == "__main__":
    main()
