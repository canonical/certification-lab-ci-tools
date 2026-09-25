"""Upgrade a lab device and enable its Ubuntu proposed pocket."""

import json
import os
import re
import textwrap
from argparse import ArgumentParser
from collections import namedtuple
from urllib.parse import urlparse

from toolbox.devices.lab import LabDevice
from toolbox.interfaces.debs import DebInterface
from toolbox.interfaces.reboot import RebootInterface
from toolbox.interfaces.status import SystemStatusInterface
from toolbox.retries import Linear

PPAData = namedtuple("PPAData", ["url", "username", "password", "key", "is_ppa"])
DEFAULT_KEYRING_DIR = "/etc/apt/keyrings"


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
        return PPAData(proposed_repository(arch), None, None, None, False)
    credentials_suffix = source_package_data.replace("-", "_").upper()
    # no user/pwd/key for public ppas
    username = os.getenv(f"KERNEL_PPA_USERNAME_{credentials_suffix}")
    password = os.getenv(f"KERNEL_PPA_PASSWORD_{credentials_suffix}")
    key = os.getenv(f"KERNEL_PPA_KEY_{credentials_suffix}")
    return PPAData(package_data_source, username, password, key, True)


def pinning_preferences(series: str) -> str:
    return (
        textwrap.dedent(f"""
        Package: *
        Pin: release o=Ubuntu,a={series}
        Pin-Priority: 500
        """).strip()
        + "\n"
    )


def slugify(value: str) -> str:
    return re.sub(r'[\/\\:*?"<>| ]', "-", value)


def ppa_url_parts(url: str) -> tuple[str, str]:
    parsed_url = urlparse(url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise SystemExit(f"Invalid PPA URL: {url}")
    path = parsed_url.path.strip("/")
    if not path:
        raise SystemExit(f"Invalid PPA URL: {url}")
    return parsed_url.netloc, path


def discover_public_ppa_key(device, url: str) -> str:
    host, path = ppa_url_parts(url)
    parts = path.split("/")
    if host != "ppa.launchpadcontent.net" or len(parts) < 2:
        raise SystemExit("PPA key is required for this repository")

    owner, archive = parts[:2]
    api_url = f"https://api.launchpad.net/1.0/~{owner}/+archive/ubuntu/{archive}"
    result = device.run(["wget", "-qO-", api_url], hide=True)
    if not result:
        raise SystemExit(
            f"ERROR: failed to retrieve the PPA signing key: {result.stderr.strip()}"
        )
    try:
        key = json.loads(result.stdout)["signing_key_fingerprint"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise SystemExit("ERROR: Launchpad did not return a PPA signing key") from error
    return key


def add_ppa_key(device, key: str) -> str:
    key = key.upper()
    keyring_file = f"{DEFAULT_KEYRING_DIR}/{key}.gpg"
    armored_key = f"/tmp/{key}.asc"
    keyserver_url = "https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x" + key
    result = device.run(["sudo", "install", "-d", "-m", "0755", DEFAULT_KEYRING_DIR])
    if not result:
        raise SystemExit(
            "ERROR: failed to create the apt keyring directory: "
            f"{result.stderr.strip()}"
        )
    result = device.run(["wget", "-q", "-O", armored_key, keyserver_url])
    if not result:
        raise SystemExit(
            f"ERROR: failed to download the PPA signing key: {result.stderr.strip()}"
        )
    try:
        result = device.run(
            [
                "sudo",
                "gpg",
                "--batch",
                "--yes",
                "--dearmor",
                "--output",
                keyring_file,
                armored_key,
            ]
        )
        if not result:
            raise SystemExit(
                f"ERROR: failed to install the PPA signing key: {result.stderr.strip()}"
            )
    finally:
        device.run(["rm", "-f", armored_key], hide=True)
    return keyring_file


def create_apt_auth_file(device, ppa_data: PPAData) -> None:
    host, path = ppa_url_parts(ppa_data.url)
    auth_file = f"/etc/apt/auth.conf.d/ppa-{slugify(path)}.conf"
    contents = textwrap.dedent(f"""
        machine {host}/{path}
        login {ppa_data.username}
        password {ppa_data.password}
        """)
    if not device.write_remote_file(auth_file, contents):
        raise SystemExit(f"ERROR: failed to write {auth_file}")
    result = device.run(["sudo", "chmod", "0600", auth_file])
    if not result:
        raise SystemExit(
            f"ERROR: failed to secure {auth_file}: {result.stderr.strip()}"
        )


def enable_ppa(device, ppa_data: PPAData, series: str) -> None:
    if bool(ppa_data.username) != bool(ppa_data.password):
        raise SystemExit("PPA username and password must both be provided")

    host, path = ppa_url_parts(ppa_data.url)
    is_private = host == "private-ppa.launchpadcontent.net"
    if is_private and not ppa_data.username:
        raise SystemExit("Private PPA credentials are required")
    if ppa_data.username:
        create_apt_auth_file(device, ppa_data)

    key = ppa_data.key or discover_public_ppa_key(device, ppa_data.url)
    keyring_file = add_ppa_key(device, key)
    sources_list_file = f"/etc/apt/sources.list.d/{slugify(path)}.list"
    contents = f"deb [signed-by={keyring_file}] {ppa_data.url} {series} main\n"
    if not device.write_remote_file(sources_list_file, contents):
        raise SystemExit(f"ERROR: failed to write {sources_list_file}")

    pin_packages(device, series)


def pin_packages(device, series: str) -> None:
    print("Pinning package priority...")
    pinning_path = "/etc/apt/preferences.d/pining"
    if not device.write_remote_file(pinning_path, pinning_preferences(series)):
        raise SystemExit(f"ERROR: failed to write {pinning_path}")


def enable_archive_proposed(device, ppa_data, series):
    print("Enabling proposed pocket...")

    proposed_repositories_list_path = (
        "/etc/apt/sources.list.d/proposed-repositories.list"
    )

    series = f"{series}-proposed"

    if not device.write_remote_file(
        proposed_repositories_list_path,
        f"deb {ppa_data.url} {series} main restricted universe multiverse\n",
    ):
        raise SystemExit(f"ERROR: failed to write {proposed_repositories_list_path}")

    pin_packages(device, series)


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
    device.interfaces[RebootInterface].reboot()
    if not device.interfaces[SystemStatusInterface].wait_for_status(
        allowed={"degraded"}, policy=Linear(times=19, delay=10)
    ):
        raise SystemExit("ERROR: device did not return after reboot")

    ppa_data = package_data_to_ppa_data(args.arch)
    print(f"Desired proposed URL: {ppa_data.url}")
    if ppa_data.is_ppa:
        enable_ppa(device, ppa_data, args.series)
    else:
        enable_archive_proposed(device, ppa_data, args.series)
    if not debs.update():
        raise SystemExit("ERROR: apt-get update failed")
    if not debs.install([os.environ["CONCRETE_KERNEL"]]):
        raise SystemExit("ERROR: kernel installation failed")


if __name__ == "__main__":
    main()
