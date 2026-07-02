"""Verify that the device under test booted the expected kernel.

Reads ``/proc/version_signature`` from the lab device over SSH (via the toolbox
``LabDevice``) and checks that the booted kernel matches the version that was
installed from -proposed. Only the command that reads the signature runs on the
device; the parsing and comparison happen on the agent. Exits with a non-zero
status when the booted version cannot be determined or does not match the
expected version, so the caller can fail the job.
"""

from argparse import ArgumentParser
import sys

from toolbox.devices.lab import LabDevice

VERSION_SIGNATURE_PATH = "/proc/version_signature"


def parse_booted_version(version_signature: str) -> str:
    """Return the booted kernel version+flavour from a version signature.

    ``/proc/version_signature`` looks like ``Ubuntu 6.8.0-130.130-generic
    6.8.12`` and the second field (``6.8.0-130.130-generic``) is the booted
    kernel version together with its flavour. An empty string is returned when
    the signature does not contain that field.
    """
    fields = version_signature.split()
    if len(fields) < 2:
        return ""
    return fields[1]


def booted_expected_kernel(booted_version_flavour: str, expected_version: str) -> bool:
    """Return True if the booted kernel matches the expected version.

    ``expected_version`` (e.g. ``6.8.0-130.130``) does not include the flavour,
    so the booted version+flavour must start with ``<expected_version>-``.
    """
    return booted_version_flavour.startswith(f"{expected_version}-")


def main():
    parser = ArgumentParser(
        description="Verify the device under test booted the expected kernel"
    )
    parser.add_argument(
        "expected_version",
        help="the kernel version expected to be booted, e.g. 6.8.0-130.130",
    )
    args = parser.parse_args()

    device = LabDevice()
    result = device.run(f"cat {VERSION_SIGNATURE_PATH}")
    if result.failed:
        print(
            f"ERROR: could not read {VERSION_SIGNATURE_PATH} on {device.host}: "
            f"{result.stderr.strip()}"
        )
        sys.exit(1)

    version_signature = result.stdout.strip()
    booted_version_flavour = parse_booted_version(version_signature)
    print("Kernel verification (active kernel):")
    print(f"  version_signature : {version_signature}")
    print(f"  booted version    : {booted_version_flavour}")
    print(f"  expected version  : {args.expected_version}")
    if not booted_version_flavour:
        print(
            "ERROR: could not determine the booted kernel version from "
            f"{VERSION_SIGNATURE_PATH}"
        )
        sys.exit(1)
    if not booted_expected_kernel(booted_version_flavour, args.expected_version):
        print(
            f"ERROR: booted kernel version {booted_version_flavour} does not "
            f"match the expected version {args.expected_version}; the device "
            "did not boot the expected kernel"
        )
        sys.exit(1)
    print(
        "Kernel verification OK: device booted expected kernel "
        f"{args.expected_version} ({booted_version_flavour})"
    )


if __name__ == "__main__":
    main()
