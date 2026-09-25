"""Upgrade a lab device and enable its Ubuntu proposed pocket."""

import json
import os
import subprocess
import textwrap
from argparse import ArgumentParser
from collections import namedtuple
from pathlib import Path

from toolbox.devices.lab import LabDevice
from toolbox.interfaces.debs import DebInterface
from toolbox.interfaces.reboot import RebootInterface
from toolbox.interfaces.status import SystemStatusInterface
from toolbox.retries import Linear

PPAData = namedtuple("PPAData", ["url", "username", "password", "key"])


try:
    PACKAGE_DATA_MAP = json.loads(os.getenv("PACKAGE_DATA_MAP", "{}"))
except json.JSONDecodeError as e:
    raise SystemExit(
        textwrap.dedent(f"""
            Unable to install kernel. Invalid PACKAGE_DATA_MAP provided:
            {e}
            Provided JSON:
            {e.doc}
            """).strip()
    )


def proposed_repository(arch: str) -> str:
    if arch in {"amd64", "i386"}:
        return "http://archive.ubuntu.com/ubuntu/"
    return "http://ports.ubuntu.com/ubuntu-ports"


def package_data_to_ppa_data(arch: str):
    """
    Get the target PPA metadata from the environment

    The relevant PPA metadata depends on the given package data that triggered
    the job. The contract is that
    """
    source_package_data = os.getenv("SOURCE_PACKAGE_DATA", "cert-package-data")
    try:
        package_data_source = PACKAGE_DATA_MAP[source_package_data]
    except KeyError:
        raise SystemExit(
            f"Unknown package-data '{source_package_data}': Update add_kernel_ppa.py"
        )
    if not package_data_source:
        # default is archive proposed
        return PPAData(proposed_repository(arch), None, None, None)
    credentials_suffix = source_package_data.replace("-", "_").upper()
    # no user/pwd/key for public ppas
    username = os.getenv(f"KERNEL_PPA_USERNAME_{credentials_suffix}", "")
    password = os.getenv(f"KERNEL_PPA_PASSWORD_{credentials_suffix}", "")
    key = os.getenv(f"KERNEL_PPA_KEY_{credentials_suffix}", "")
    return PPAData(package_data_source, username, password, key)


def pinning_preferences(series: str) -> str:
    return (
        textwrap.dedent(f"""
        Package: *
        Pin: release o=Ubuntu,a={series}-proposed
        Pin-Priority: 500
        """).strip()
        + "\n"
    )


def enable_public_ppa(device, url, series):
    print("Enabling proposed pocket...")

    proposed_repositories_list_path = (
        "/etc/apt/sources.list.d/proposed-repositories.list"
    )
    if not device.write_remote_file(
        proposed_repositories_list_path,
        f"deb {url} {series}-proposed main restricted universe multiverse\n",
    ):
        raise SystemExit(f"ERROR: failed to write {proposed_repositories_list_path}")

    print("Pinning package priority...")
    pinning_path = "/etc/apt/preferences.d/pining"
    if not device.write_remote_file(pinning_path, pinning_preferences(series)):
        raise SystemExit(f"ERROR: failed to write {pinning_path}")


def enable_private_ppa(device, ppa_data: PPAData):
    # TODO: replace this legacy script/check_calls with everything done in
    # this one instead
    debs = device.interfaces[DebInterface]
    tools_path = Path(os.getenv("TOOLS_PATH", ""))
    subprocess.check_call(
        [
            "_put",
            tools_path / "add_private_ppa.py",
            tools_path / "kernel-switcher.py",
            ":",
        ]
    )
    device.run(
        [
            "sudo",
            "./add_private_ppa.py",
            ppa_data.url,
            ppa_data.username,
            ppa_data.password,
            ppa_data.key,
        ]
    )
    debs.update()
    debs.install(os.environ["CONCRETE_KERNEL"])
    # FIXME: find a way to get the kernel name so we can force boot to it
    # device.run(["sudo", "./switch_kernel.py" ...])


def parse_args():
    parser = ArgumentParser(
        description="Upgrade a lab device and enable its Ubuntu proposed pocket"
    )
    parser.add_argument("arch", help="Ubuntu architecture, for example amd64 or arm64")
    parser.add_argument("series", help="Ubuntu series codename, for example noble")
    return parser.parse_args()


def ensure_environment():
    if not os.getenv("PACKAGE_DATA_MAP"):
        raise SystemExit("Script requires 'PACKAGE_DATA_MAP' to be defined")


def main():
    args = parse_args()
    ensure_environment()

    device = LabDevice(
        interfaces=[DebInterface(), RebootInterface(), SystemStatusInterface()]
    )
    debs = device.interfaces[DebInterface]
    if not debs.update():
        raise SystemExit("ERROR: apt-get update failed")
    if not debs.upgrade(options=["--allow-remove-essential"]):
        raise SystemExit("ERROR: apt-get dist-upgrade failed")

    device.interfaces[RebootInterface].reboot()
    if not device.interfaces[SystemStatusInterface].wait_for_status(
        allowed={"degraded"}, policy=Linear(times=19, delay=10)
    ):
        raise SystemExit("ERROR: device did not return after reboot")

    ppa_data = package_data_to_ppa_data(args.arch)
    print(f"Desired proposed URL: {ppa_data.url}")
    if ppa_data.username is None:
        enable_public_ppa(device, ppa_data.url, args.series)
    else:
        enable_private_ppa(device, ppa_data)


if __name__ == "__main__":
    main()
