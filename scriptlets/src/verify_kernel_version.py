#!/usr/bin/env python3
"""Verify that the device under test booted the expected kernel.

This scriptlet is copied onto the device under test and executed there. It
reads ``/proc/version_signature`` and checks that the booted kernel matches the
version that was installed from -proposed. It exits with a non-zero status when
the booted version cannot be determined or does not match the expected version,
so the caller can fail the job.
"""

import argparse
import sys
from collections.abc import Sequence

EXIT_OK = 0
EXIT_FAILURE = 1


def parse_booted_version(version_signature: str) -> str:
    """Return the booted kernel version+flavour from a version signature.

    ``/proc/version_signature`` looks like::

        Ubuntu 6.8.0-130.130-generic 6.8.12

    and the second field (``6.8.0-130.130-generic``) is the booted kernel
    version together with its flavour. An empty string is returned when the
    signature does not contain that field.
    """
    fields = version_signature.split()
    if len(fields) < 2:
        return ""
    return fields[1]


def booted_expected_kernel(
    booted_version_flavour: str, expected_version: str
) -> bool:
    """Return True if the booted kernel matches the expected version.

    ``expected_version`` (e.g. ``6.8.0-130.130``) does not include the flavour,
    so the booted version+flavour must start with ``<expected_version>-``.
    """
    return booted_version_flavour.startswith(f"{expected_version}-")


def verify(version_signature: str, expected_version: str) -> int:
    """Verify the booted kernel.

    Prints human-readable lines describing the outcome as it goes and returns
    an exit code (``EXIT_OK`` or ``EXIT_FAILURE``).
    """
    booted_version_flavour = parse_booted_version(version_signature)
    print("Kernel verification (active kernel):")
    print(f"  version_signature : {version_signature}")
    print(f"  booted version    : {booted_version_flavour}")
    print(f"  expected version  : {expected_version}")
    if not booted_version_flavour:
        print(
            "ERROR: could not determine the booted kernel version from "
            "/proc/version_signature"
        )
        return EXIT_FAILURE
    if not booted_expected_kernel(booted_version_flavour, expected_version):
        print(
            f"ERROR: booted kernel version {booted_version_flavour} does not "
            f"match the expected version {expected_version}; the device did "
            "not boot the expected kernel"
        )
        return EXIT_FAILURE
    print(
        "Kernel verification OK: device booted expected kernel "
        f"{expected_version} ({booted_version_flavour})"
    )
    return EXIT_OK


def read_version_signature(path: str = "/proc/version_signature") -> str:
    with open(path, encoding="utf-8") as version_file:
        return version_file.read().strip()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "expected_version",
        help="the kernel version expected to be booted, e.g. 6.8.0-130.130",
    )
    args = parser.parse_args(argv)

    return verify(read_version_signature(), args.expected_version)


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
