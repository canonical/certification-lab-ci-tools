from argparse import ArgumentParser

from toolbox.checkbox.installers.debs import CheckboxDebsInstaller
from toolbox.devices import LocalHost
from toolbox.devices.lab import LabDevice
from toolbox.entities.risk import Risk
from toolbox.interfaces.debs import DebInterface


def main():
    parser = ArgumentParser(
        description="Install Checkbox on device (from debs) and agent (from source)"
    )
    parser.add_argument(
        "risk",
        choices=[risk.value for risk in Risk],
        help="Risk level for the checkbox-dev PPA",
    )
    parser.add_argument(
        "--providers",
        nargs="+",
        help="Specify additional provider packages",
    )
    args = parser.parse_args()

    device = LabDevice(interfaces=[DebInterface()])
    installer = CheckboxDebsInstaller(
        device=device,
        agent=LocalHost(),
        risk=Risk(args.risk),
        providers=args.providers,
    )
    installer.install()


if __name__ == "__main__":
    main()
