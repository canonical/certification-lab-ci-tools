"""Download Google's signing keys and install them on the DUT for APT.

Uses DEVICE_IP, DEVICE_USER and DEVICE_PWD through LabDevice. Always refreshes
the key, regardless of whether Chrome is installed. Failures exit nonzero.
"""

import io
from urllib.error import URLError
from urllib.request import urlopen

from toolbox.devices.lab import LabDevice

KEY_URL = "https://dl.google.com/linux/linux_signing_key.pub"
KEY_PATH = "/etc/apt/trusted.gpg.d/google.asc"

# Stage the download beside the destination so a failed write cannot truncate
# the existing key. Rename only after the write and permissions succeed.
INSTALL_KEY = f"""set -eu
key_tmp=$(mktemp {KEY_PATH}.XXXXXX)
trap 'rm -f "$key_tmp"' EXIT
cat > "$key_tmp"
chmod 0644 "$key_tmp"
mv -f "$key_tmp" {KEY_PATH}
"""


def main():
    try:
        device = LabDevice()
    except RuntimeError as error:
        raise SystemExit(f"ERROR: {error}") from error

    print(f"Refreshing Google's signing key on {device.host}...")
    try:
        with urlopen(KEY_URL, timeout=30) as response:
            key = response.read().decode("ascii")
    except (URLError, OSError, UnicodeError) as error:
        raise SystemExit(
            f"ERROR: Failed to download Google's signing key: {error}"
        ) from error

    if (
        "-----BEGIN PGP PUBLIC KEY BLOCK-----" not in key
        or "-----END PGP PUBLIC KEY BLOCK-----" not in key
    ):
        raise SystemExit("ERROR: Download did not contain a PGP public key")

    result = device.run(
        ["sudo", "sh", "-c", INSTALL_KEY],
        in_stream=io.StringIO(key),
        hide=True,
    )
    if result.failed:
        raise SystemExit(
            f"ERROR: Failed to install Google's signing key on {device.host}: "
            f"{result.stderr.strip()}"
        )
    print(f"Installed Google's signing key at {KEY_PATH}.")


if __name__ == "__main__":
    main()
