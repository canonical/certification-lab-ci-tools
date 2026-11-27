"""Prepare DUT before running tests."""

import os
from argparse import ArgumentParser

from toolbox.devices.lab import LabDevice

DEVICE_SCRIPTLETS = (
    "retry",
    "install_packages",
    "clean_machine",
    "git_get_shallow",
)


def ensure_remote_dir(device: LabDevice, remote_path: str):
    """Ensure that the specified directory exists on the remote device.

    :param device: LabDevice instance representing the device under test.
    :param remote_path: Path on the remote device to ensure existence.
    """
    result = device.run(["mkdir", "-p", remote_path], hide=True)
    if result.failed:
        raise SystemExit(
            f"ERROR: could not create directory '{remote_path}' on {device.host}: "
            f"{result.stderr.strip()}"
        )


def put_scriptlets(device: LabDevice, local_path: str, remote_path: str):
    """Copy scriptlets to the device under test.

    :param device: LabDevice instance representing the device under test.
    :param local_path: Path to the local directory containing scriptlets to copy.
    :param remote_path: Path on the remote device where scriptlets will be copied.
    """
    ensure_remote_dir(device, remote_path)
    print(f"Copying scriptlets to {device.host}:{remote_path}...")
    result = device.put(
        local_paths=[os.path.join(local_path, name) for name in DEVICE_SCRIPTLETS],
        remote_dir=remote_path,
    )
    if result.failed:
        raise SystemExit(
            f"ERROR: could not copy scriptlets to {device.host}: "
            f"{result.stderr.strip()}"
        )
    print(result.stdout)


def main():
    parser = ArgumentParser(
        description="Prepare the device under test before running tests",
    )
    parser.add_argument(
        "--local-path",
        help="Path to the local directory containing scriptlets to copy",
        default=os.environ.get("SCRIPTLETS_PATH"),
    )
    parser.add_argument(
        "--remote-path",
        help="Path on the remote device (relative paths resolve from home)",
        default=os.environ.get("TOOLS_PATH_DEVICE"),
    )
    args = parser.parse_args()
    if not args.local_path:
        raise SystemExit(
            "ERROR: local-path is not specified and SCRIPTLETS_PATH is not set"
        )
    if not os.path.isdir(args.local_path):
        raise SystemExit(f"ERROR: '{args.local_path}' is not a directory")
    if not args.remote_path:
        raise SystemExit(
            "ERROR: remote-path is not specified and TOOLS_PATH_DEVICE is not set"
        )

    try:
        device = LabDevice()
    except RuntimeError as error:
        raise SystemExit(f"ERROR: {error}") from error
    put_scriptlets(device, args.local_path, args.remote_path)


if __name__ == "__main__":
    main()
