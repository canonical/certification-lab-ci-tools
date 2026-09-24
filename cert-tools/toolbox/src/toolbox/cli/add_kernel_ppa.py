"""Upgrade a lab device and enable its Ubuntu proposed pocket."""

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

# maps package data name to the ppa url
# See: # https://docs.google.com/document/d/1-6yP0_iXrslAQFTGaP7ioPhSSYaCn39dVY9Oy_qXW9s/edit?usp=sharing
private_ppa = "https://private-ppa.launchpadcontent.net"
public_ppa = "https://ppa.launchpadcontent.net"

PACKAGE_DATA_MAP = {
    "cert-package-data": None,
    "cert-package-data-proposed2": f"{public_ppa}/canonical-kernel-team/proposed2/ubuntu",
    "cert-package-data-proposed3": f"{public_ppa}/canonical-kernel-team/proposed3/ubuntu",
    "cert-esm-pakcage-data-proposed": f"{private_ppa}/canonical-kernel-esm/proposed/ubuntu",
    "cert-esm-pakcage-data-proposed2": f"{private_ppa}/canonical-kernel-esm/proposed2/ubuntu",
    "cert-esm-pakcage-data-proposed3": f"{private_ppa}/canonical-kernel-esm/proposed3/ubuntu",
    "cert-realtime-package-data": f"{private_ppa}/ubuntu-advantage/realtime-proposed/ubuntu",
    "cert-realtime-package-data2": f"{private_ppa}/canonical-kernel-rt/proposed2/ubuntu",
    "cert-realtime-package-data-proposed3": f"{private_ppa}/canonical-kernel-rt/proposed3/ubuntu",
    "cert-koto-package-data": f"{private_ppa}/canonical-hwe-private/renesas-proposed/ubuntu",
    "cert-fips-updates-package-data": f"{private_ppa}/ubuntu-advantage/pro-fips-updates/ubuntu",
}


def proposed_repository(arch: str) -> str:
    if arch in {"amd64", "i386"}:
        return "http://archive.ubuntu.com/ubuntu/"
    return "http://ports.ubuntu.com/ubuntu-ports"


def package_data_to_ppa_data(arch: str):
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
    try:
        credentials_suffix = int(source_package_data[-1])
    except ValueError:
        credentials_suffix = ""
    # no user/pwd/key for public ppas
    username = os.getenv(f"KERNEL_PPA_USERNAME{credentials_suffix}", "")
    password = os.getenv(f"KERNEL_PPA_PASSWORD{credentials_suffix}", "")
    key = os.getenv(f"KERNEL_PPA_KEY{credentials_suffix}", "")
    return PPAData(package_data_source, username, password, key)


def pinning_preferences(series: str) -> str:
    return textwrap.dedent(f"""
        Package: *
        Pin: release o=Ubuntu,a={series}-proposed
        Pin-Priority: 500
        """).strip() + "\n"


def enable_archive_proposed(device, url, series):
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


def main():
    parser = ArgumentParser(
        description="Upgrade a lab device and enable its Ubuntu proposed pocket"
    )
    parser.add_argument("arch", help="Ubuntu architecture, for example amd64 or arm64")
    parser.add_argument("series", help="Ubuntu series codename, for example noble")
    args = parser.parse_args()

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
    if ppa_data.username is None:
        enable_archive_proposed(device, ppa_data.url, args.series)
        return
    # TODO: replace this legacy script/check_calls with everything done in
    # this one instead
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


if __name__ == "__main__":
    main()
