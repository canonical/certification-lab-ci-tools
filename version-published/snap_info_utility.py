"""
This module contains every utility function shared among multiple
scripts that fetches information about snaps
"""

import re
import requests

from packaging import version
from subprocess import check_output


def get_snap_info_from_store(snap_name: str) -> dict:
    """
    Get detailed information about a snap using the info endpoint.

    :param snap_spec: the snap specification
    :return: deserialised json with the response from the snap store
    """
    url = f"https://api.snapcraft.io/v2/snaps/info/{snap_name}"
    headers = {"Snap-Device-Series": "16", "Snap-Device-Store": "ubuntu"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise RuntimeError(
            f"Failed to get info about {snap_name} from the snap store."
        )

    return response.json()


def get_history_since(tag: str, repo_path: str):
    return check_output(
        [
            "git",
            "log",
            "--pretty=format:%H",
            "--no-patch",
            f"{tag}~1..origin/main",
        ],
        text=True,
        cwd=repo_path,
    ).splitlines()


def get_version_and_offset(version_str: str):
    # Use regex to match the version pattern and extract the base version
    # and dev number if present (e.g. v1.2.3-dev45, 1.2.3.dev45, 1.2.3)
    # the v at the beginning is optional
    match = re.match(r"^v?(\d+\.\d+\.\d+).?(?:dev(\d+))?$", version_str)
    if match:
        base_version = f"v{match.group(1)}"
        dev_number = match.group(2) if match.group(2) else "0"
        return base_version, int(dev_number)
    else:
        raise ValueError(f"Invalid version format: {version_str}")


def get_previous_tag(base_version: str, repo_path: str):
    # Get the list of tags sorted by creation date
    tags = check_output(
        ["git", "tag", "--sort=-creatordate"], cwd=repo_path, text=True
    ).splitlines()

    # Filter the list of tags to only include the ones that match the version
    # pattern
    tags = [tag for tag in tags if re.match(r"^v\d+\.\d+\.\d+$", tag)]

    # Get the previous tag corresponding to the base version. We have to do it
    # this way because the tags are only created once the version is published.
    # For example, 4.0.0.dev333 will use the previous tag v3.3.0 to calculate
    # the offset, not v4.0.0. The versions after 4.0.0 will use v4.0.0.
    previous_tag = None
    for t in tags:
        if version.parse(t) < version.parse(base_version):
            previous_tag = t
            break

    if not previous_tag:
        raise SystemExit(
            f"Unable to locate a previous tag for the version: {base_version}"
        )

    return previous_tag


def get_revision_at_offset(version_str: str, repo_path: str):
    base_version, offset = get_version_and_offset(version_str)
    previous_tag = get_previous_tag(base_version, repo_path)
    history = get_history_since(previous_tag, repo_path)
    print(
        f"Checkout to {offset} commits after the preceding tag {previous_tag}"
    )
    # history is HEAD -> latest_tag(included)
    # reverse it so it tag -> HEAD
    history = list(reversed(history))
    # so now 0 is tag
    #        1 is the commit after the tag
    #        len(history) -1 is HEAD
    try:
        return history[offset]
    except IndexError:
        raise SystemExit(
            f"Unable to locate the commit that generated version: {version_str}"
        )
