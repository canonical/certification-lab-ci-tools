#!/usr/bin/env python3
"""
This script moves a branch HEAD from the current location
to an offset calculated from a version string in the form
of vX.Y.Z-devAA, where AA is the ammount of commits

Example usage:
    python3 move_beta_branch.py repository_path beta_validation version_string
"""

import sys
from argparse import ArgumentParser, ArgumentTypeError
from subprocess import check_call

from snap_info_utility import get_revision_at_offset


def move_branch_head(branch_name, revision, repo_path: str):
    check_call(["git", "checkout", branch_name], cwd=repo_path)
    check_call(["git", "reset", "--hard", revision], cwd=repo_path)
    # Note: the update should move the branch HEAD ahead. If this is
    #       the case, there is no need to push --force, else something
    #       went terribly wrong, we must fail here
    check_call(["git", "push", "origin", branch_name], cwd=repo_path)


def move_beta_branch(branch_name: str, version: str, repo_path: str):
    target_revision = get_revision_at_offset(version, repo_path)
    move_branch_head(branch_name, target_revision, repo_path)


def parse_args(argv):
    def version_validator_type(arg):
        if "dev" in arg:
            return arg
        raise ArgumentTypeError(f"{arg} is not a valid version")

    parser = ArgumentParser()
    parser.add_argument("repository_path", help="Path to the repository")
    parser.add_argument("branch_name", help="Name of the branch to move")
    parser.add_argument(
        "version",
        help="Version string in the format vX.Y.Z-devAA",
        type=version_validator_type,
    )
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    move_beta_branch(args.branch_name, args.version, args.repository_path)


if __name__ == "__main__":
    main(sys.argv[1:])
