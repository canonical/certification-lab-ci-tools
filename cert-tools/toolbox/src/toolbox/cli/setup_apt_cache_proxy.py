"""Configure a DUT to use the lab apt-cache proxy.

Writes ``/etc/apt/apt.conf.d/02proxy`` on the remote device so that APT HTTP
traffic is routed through the ``cert-apt-cache`` proxy while HTTPS traffic goes
DIRECT. Ubuntu Core devices are skipped (they have no apt). All error paths exit
0 with a descriptive SKIP/ERROR message so that SRU tests are not aborted.

Passing the ``disable`` action removes ``/etc/apt/apt.conf.d/02proxy`` from
the remote device so that APT no longer uses the proxy.

The IP of the device is provided by the environment variable ``DEVICE_IP``,
which must be set. The user name on the remote device defaults to ``ubuntu``
unless provided by the environment variable ``DEVICE_USER``. Password-based
authentication is used when ``DEVICE_PWD`` is set.

The cache host defaults to ``tel-apt-cache.canonical.com`` and can be overridden
via the ``APT_CACHE_HOST`` environment variable.

Usage::

    DEVICE_IP=<dut-ip> setup_apt_cache_proxy
    APT_CACHE_HOST=<host> DEVICE_IP=<dut-ip> setup_apt_cache_proxy
"""

import io
import os
import sys
from argparse import ArgumentParser

from toolbox.devices.lab import LabDevice

DEFAULT_APT_CACHE_HOST = "tel-apt-cache.canonical.com"
APT_PROXY_CONF_PATH = "/etc/apt/apt.conf.d/02proxy"
PROXY_PORT = 3142


def generate_proxy_config(cache_host: str) -> str:
    """Return the contents of the apt proxy configuration file.

    HTTP traffic is routed through ``cache_host`` on port :data:`PROXY_PORT`.
    HTTPS traffic is set to ``DIRECT`` (not cached).
    """
    return (
        f'Acquire::http::Proxy "http://{cache_host}:{PROXY_PORT}";\n'
        f'Acquire::https::Proxy "DIRECT";\n'
    )


def is_ubuntu_core(os_id: str) -> bool:
    """Return True if the OS ID string indicates Ubuntu Core."""
    return os_id.strip() == "ubuntu-core"


def enable_proxy(device: LabDevice, cache_host: str) -> None:
    """Write the apt proxy configuration file on ``device``."""
    print(f"Setting up apt-cache proxy ({cache_host}:{PROXY_PORT}) on {device.host}...")

    # Write proxy config atomically in a single run
    config = generate_proxy_config(cache_host)
    result = device.run(
        f"sudo tee {APT_PROXY_CONF_PATH} >/dev/null",
        in_stream=io.StringIO(config),
    )
    if result.failed:
        print(
            f"ERROR: Failed to write proxy config to {APT_PROXY_CONF_PATH} "
            f"on {device.host} — skipping"
        )
        sys.exit(0)

    print("Done.")


def disable_proxy(device: LabDevice) -> None:
    """Remove the apt proxy configuration file from ``device`` (if present)."""
    print(f"Removing apt-cache proxy configuration from {device.host}...")

    result = device.run(f"sudo rm -f {APT_PROXY_CONF_PATH}")
    if result.failed:
        print(
            f"ERROR: Failed to remove proxy config {APT_PROXY_CONF_PATH} "
            f"on {device.host} — skipping"
        )
        sys.exit(0)

    print("Done.")


def main():
    parser = ArgumentParser(
        description="Enable or disable the lab apt-cache proxy on the DUT"
    )
    parser.add_argument(
        "action",
        nargs="?",
        choices=["enable", "disable"],
        default="enable",
        help="enable (default) writes the proxy config, disable removes it",
    )
    args = parser.parse_args()

    cache_host = os.environ.get("APT_CACHE_HOST", DEFAULT_APT_CACHE_HOST)

    try:
        device = LabDevice()
    except RuntimeError as error:
        print(f"ERROR: {error}")
        sys.exit(1)

    # Detect OS — skip Ubuntu Core (no apt)
    result = device.run(". /etc/os-release 2>/dev/null && echo $ID")
    if result.failed:
        print(
            f"SKIP: Failed to detect OS on {device.host} "
            f"(exit code: {result.exited}) — no apt proxy configured"
        )
        sys.exit(0)

    os_id = result.stdout.strip()
    if is_ubuntu_core(os_id):
        print(f"SKIP: Ubuntu Core detected on {device.host}, no apt proxy needed")
        sys.exit(0)

    if args.action == "disable":
        disable_proxy(device)
    else:
        enable_proxy(device, cache_host)


if __name__ == "__main__":
    main()
