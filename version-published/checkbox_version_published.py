#!/usr/bin/env python3
"""
This program checks whether a specific version of Checkbox is available for a
series of snaps and if the correspondent packages are available in a given PPA

There are two matrixes of all combinations stored in a yaml file and the
program periodically checks whether all combinations are available and
waits until either all of them are available or the timeout is reached.
The first argument is the version of the snaps and packages to check for.

The characteristics for the snaps that can be specified are:
  - (required and 1) channel that all of the snaps must be in
  - (required and 1 or more) names of the snaps
  - (required and 1 or more) architectures for all of the snaps

The characteristics for the packages that can be specified are:
  - (required and 1) channel of the package (same as the PPA name)
  - (required and 1) name of the source
  - (required and 1) name of the package (.deb file)
  - (required and 1 or more) versions of ubuntu
  - (required and 1 or more) architectures


For instance, to check if the "checkbox22" related snaps are available, all
having a version of "3.3.0-dev10", for the architectures:
  - amd64
  - arm64

This effectively means we will check the availability of the following snaps:
  - checkbox22_3.3.0-dev10_amd64.snap
  - checkbox22_3.3.0-dev10_arm64.snap

The snap specs specified in the yaml look like this:
```
required-snaps:
  - name: checkbox22
    channels: [ latest/edge ]
    architectures: [ amd64, arm64 ]
```


In the same way we can check whether the packages are available in the PPA.
For "checkbox-ng" the specs specified in the yaml look like this:
```
required-packages:
  - channel: edge
    source: checkbox-ng
    package: checkbox-ng
    versions: [ "18.04", "20.04", "22.04", "24.04" ]
    architectures: [ amd64, arm64 ]
```

So, considering `checkbox-canary.yaml` contains both parts, the invocation
to check if both snaps and packages are available would be:
```
    python3 checkbox_version_published.py 3.3.0-dev10 \
    checkbox-canary.yaml --timeout 300
```
"""

import argparse
import sys
import time
from typing import NamedTuple

import requests
import yaml
from snap_info_utility import get_snap_info_from_store


# The named tuple for the snap specification.
# instance of this class represents one, concrete snap.
class SnapSpec(NamedTuple):
    name: str
    version: str
    channel: str
    arch: str


# The named tuple for the package specification.
# instance of this class represents one, concrete package in the PPA.
class PackageSpec(NamedTuple):
    channel: str
    source: str
    package: str
    version: str
    ubuntu_version: str
    arch: str


def get_snap_specs(yaml_content: dict, version: str) -> list[SnapSpec]:
    """
    Create a list of SnapSpec objects from the yaml content.
    :param yaml_content: file containing the snap requirements
    :param version: the version of the snap
    :return: the list of SnapSpec objects
    """
    required_snaps = yaml_content.get("required-snaps", [])

    snap_specs = [
        SnapSpec(snap["name"], version, channel, arch)
        for snap in required_snaps
        for channel in snap["channels"]
        for arch in snap["architectures"]
    ]
    return snap_specs


def is_snap_available(snap_spec: SnapSpec, store_response: dict) -> bool:
    """
    Process the response from the snap store and check whether the specified
    snap is available.
    :param snap_spec: the snap specification
    :param store_response: the response from the snap store
    :return: True if the snap is available, False otherwise
    """
    # let's split the "channel" provided by the user
    # into the track and the risk

    def matches_spec(channel_info: dict) -> bool:
        # some of the channel names don't follow the "track/risk" format
        # so we need to handle them separately
        if "/" not in snap_spec.channel:
            return (
                channel_info["channel"]["name"] == snap_spec.channel
                and channel_info["version"] == snap_spec.version
                and channel_info["channel"]["architecture"] in snap_spec.arch
            )
        else:
            track, risk = snap_spec.channel.split("/")
            return (
                channel_info["channel"]["track"] == track
                and channel_info["channel"]["risk"] == risk
                and channel_info["version"] == snap_spec.version
                and channel_info["channel"]["architecture"] in snap_spec.arch
            )

    return any(
        matches_spec(channel_info) for channel_info in store_response["channel-map"]
    )


def check_snaps_availability(
    snap_specs: list[SnapSpec],
    snaps_available: dict[SnapSpec, bool],
) -> None:
    print("Checking if the snaps are available ...")
    # Record of snaps for which we've already fetched the data from the store.
    # avoid re-querying the store for the same snap name. Leaving the function
    # invalidates the cache, as we expect the situation to be constantly
    # evolving
    local_store_cache = {}

    for snap_spec in snap_specs:
        # Only fetch from the store if not already fetched and not already
        # available.
        if snaps_available[snap_spec]:
            continue
        try:
            if snap_spec.name not in local_store_cache:
                local_store_cache[snap_spec.name] = get_snap_info_from_store(
                    snap_spec.name
                )
            store_response = local_store_cache[snap_spec.name]
            snaps_available[snap_spec] = is_snap_available(snap_spec, store_response)

        except (requests.RequestException, RuntimeError) as exc:
            # Handle request exceptions but continue the loop.
            print(f"Error while querying the snap store: {exc}")

    # Print the list of snaps that were not found.
    not_available = [
        snap_spec
        for snap_spec, is_available in snaps_available.items()
        if not is_available
    ]
    if not_available:
        print("Not all snaps were available in the store.")
        print("Here is the list of snaps that were not found:")
        print("name       | channel     | arch ")
        print("-" * 32)
        for snap_spec in not_available:
            print(
                f"{snap_spec.name:<10} | {snap_spec.channel:<11} | {snap_spec.arch:<5}"
            )
        print("-" * 32 + "\n")
    else:
        print("All snaps were found.")


def get_package_specs(yaml_content: dict, version: str) -> list[PackageSpec]:
    """
    Create a list of PackageSpec objects from the yaml content.
    :param yaml_content: file containing the package requirements
    :param version: the version of the package
    :return: the list of PackageSpec objects
    """
    version = version.replace("-", "~")
    required_packages = yaml_content.get("required-packages", {})

    package_specs = []
    for package in required_packages:
        # General versions and architectures
        for ubuntu_version in package["versions"]:
            for arch in package["architectures"]:
                package_specs.append(
                    PackageSpec(
                        package["channel"],
                        package["source"],
                        package["package"],
                        version,
                        ubuntu_version,
                        arch,
                    )
                )
    package_specs.sort()
    return package_specs


def check_packages_availability(
    package_specs: list[PackageSpec],
    packages_available: dict[PackageSpec, bool],
) -> None:
    print("Checking if the packages are available ...")
    # avoid re-querying LP for the same deb. Leaving the function
    # invalidates the cache, as we expect the situation to be constantly
    # evolving
    local_lp_cache = {}

    for package_spec in package_specs:
        if packages_available[package_spec]:
            continue
        url = (
            f"http://ppa.launchpad.net/checkbox-dev/{package_spec.channel}"
            f"/ubuntu/pool/main/c/{package_spec.source}"
        )
        name = (
            f"{package_spec.package}_{package_spec.version}~ubuntu"
            f"{package_spec.ubuntu_version}.1_{package_spec.arch}.deb"
        )
        if url not in local_lp_cache:
            local_lp_cache[url] = requests.get(url)
        packages_available[package_spec] = name in local_lp_cache[url].text

    # Print the list of packages that were not found.
    not_available = [
        package_spec
        for package_spec, is_available in packages_available.items()
        if not is_available
    ]
    if not_available:
        print("Not all packages were available in the PPA.")
        print("Here is the list of packages that were not found:")
        print("name                                   | ubuntu version | arch")
        print("-" * 66)
        for package_spec in not_available:
            print(
                f"{package_spec.package:<38} | "
                f"{package_spec.ubuntu_version:<14} | "
                f"{package_spec.arch:<5}"
            )
        print("-" * 66 + "\n")
    else:
        print("All packages were found.")


def check_availability(snap_specs: list, package_specs: list, timeout: int) -> None:
    # Dict to store whether each snap and package is available.
    snaps_available = {snap_spec: False for snap_spec in snap_specs}
    packages_available = {package_spec: False for package_spec in package_specs}
    # Set the deadline.
    deadline = time.time() + timeout
    while True:
        if not all(snaps_available.values()):
            check_snaps_availability(snap_specs, snaps_available)
        if not all(packages_available.values()):
            check_packages_availability(package_specs, packages_available)

        # Exit the loop if all snaps and/or packages are found.
        if all(snaps_available.values()) and all(packages_available.values()):
            break

        # Exit the loop if the timeout is reached.
        if time.time() > deadline:
            raise TimeoutError("Timeout reached.")

        print("--- Waiting 30 seconds before retrying ---\n")
        # Wait before the next iteration.
        time.sleep(30)
    print("All snaps/packages for the specific version were found.")


def main(argv):
    parser = argparse.ArgumentParser(
        description="Check whether snaps are available in the snap store."
    )
    parser.add_argument("version", help="Version of checkbox to check for.")
    parser.add_argument(
        "checkbox_yaml",
        type=argparse.FileType("r"),
        help="Path to the YAML file specifying the snap requirements.",
    )
    parser.add_argument(
        "--timeout",
        help="Timeout in seconds after which the program will stop checking.",
        default=300,
        type=int,
    )
    args = parser.parse_args(argv[1:])

    yaml_content = yaml.load(args.checkbox_yaml, Loader=yaml.FullLoader)

    if not isinstance(yaml_content, dict):
        raise ValueError("The YAML content is invalid.")

    snap_specs = get_snap_specs(yaml_content, args.version)
    package_specs = get_package_specs(yaml_content, args.version)

    check_availability(snap_specs, package_specs, args.timeout)


if __name__ == "__main__":
    main(sys.argv)
