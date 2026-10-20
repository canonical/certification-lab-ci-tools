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

A repository that publishes an ``http://`` URL and redirects to HTTPS can never
be completed by the cache — it speaks HTTP only — and the cache unit cannot reach
every host either. Such hosts are pinned to ``DIRECT`` with
``Acquire::http::Proxy::<host>``, the finest granularity APT offers: it keys
proxies by host, not by path. :data:`DEFAULT_DIRECT_HOSTS` starts with the one
host the lab hit; ``APT_CACHE_DIRECT_HOSTS`` (comma separated, empty to disable)
replaces the list per run.

A source written in the legacy ``http://HTTPS///host/path`` form is NOT rewritten
here: the vendor owns that file, and rewriting it would be undone by the next
vendor update. That form asks the proxy to open a TLS tunnel, which apt-cacher-ng
implements — so the cache needs egress to the host, not a client-side change.

Usage::

    DEVICE_IP=<dut-ip> setup_apt_cache_proxy
    APT_CACHE_HOST=<host> DEVICE_IP=<dut-ip> setup_apt_cache_proxy
    APT_CACHE_DIRECT_HOSTS=<host>[,<host>...] DEVICE_IP=<dut-ip> setup_apt_cache_proxy
"""

import io
import os
import sys
from argparse import ArgumentParser

from toolbox.devices.lab import LabDevice

DEFAULT_APT_CACHE_HOST = "tel-apt-cache.canonical.com"
APT_PROXY_CONF_PATH = "/etc/apt/apt.conf.d/02proxy"
PROXY_PORT = 3142

#: Environment variable that replaces :data:`DEFAULT_DIRECT_HOSTS` (comma
#: separated; empty means "no exceptions").
DIRECT_HOSTS_ENV = "APT_CACHE_DIRECT_HOSTS"

#: Repositories the DUT must fetch itself.
#:
#: ``dl.google.com`` publishes an ``http://`` URL that redirects to HTTPS, which
#: the HTTP-only cache cannot follow, and the cache unit cannot reach it at all.
#: Every other repository keeps going through the cache — including the legacy
#: ``http://HTTPS///host/path`` sources (NVIDIA's Jetson drop-in), which need
#: egress from the cache rather than a client-side exception.
DEFAULT_DIRECT_HOSTS = ("dl.google.com",)


def generate_proxy_config(cache_host: str, direct_hosts=DEFAULT_DIRECT_HOSTS) -> str:
    """Return the contents of the apt proxy configuration file.

    HTTP traffic is routed through ``cache_host`` on port :data:`PROXY_PORT`.
    HTTPS traffic is set to ``DIRECT`` (not cached). Every host in
    ``direct_hosts`` gets its own ``Acquire::http::Proxy::<host> "DIRECT"`` line,
    so the DUT fetches it itself — the only way a repository that redirects to
    HTTPS, or that the cache cannot reach, can work.
    """
    lines = [
        f'Acquire::http::Proxy "http://{cache_host}:{PROXY_PORT}";',
        'Acquire::https::Proxy "DIRECT";',
    ]
    for host in direct_hosts or ():
        host = host.strip()
        if host:
            lines.append(f'Acquire::http::Proxy::{host} "DIRECT";')
    return "\n".join(lines) + "\n"


def is_ubuntu_core(os_id: str) -> bool:
    """Return True if the OS ID string indicates Ubuntu Core."""
    return os_id.strip() == "ubuntu-core"


def direct_hosts_from_env(value, *, default=DEFAULT_DIRECT_HOSTS) -> tuple:
    """Parse ``APT_CACHE_DIRECT_HOSTS``.

    Unset keeps the defaults; an empty string means "no exceptions", so an
    operator can turn the whole mechanism off without editing code.
    """
    if value is None:
        return tuple(default)
    return tuple(host.strip() for host in str(value).split(",") if host.strip())


def enable_proxy(device: LabDevice, cache_host: str, direct_hosts=None) -> None:
    """Write the apt proxy configuration file on ``device``."""
    print(f"Setting up apt-cache proxy ({cache_host}:{PROXY_PORT}) on {device.host}...")

    # Write proxy config atomically in a single run
    config = generate_proxy_config(
        cache_host,
        DEFAULT_DIRECT_HOSTS if direct_hosts is None else direct_hosts,
    )
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
    direct_hosts = direct_hosts_from_env(os.environ.get(DIRECT_HOSTS_ENV))

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
        enable_proxy(device, cache_host, direct_hosts)


if __name__ == "__main__":
    main()
