#!/usr/bin/env python3
#
# Copyright 2024 Canonical Ltd.
# Written by:
#   Fernando Bravo <fernando.bravo.hernandez@canonical.com>

"""
Tools to download a list of submissions from the certification website.

Example of a submission URL:
https://certification.canonical.com/hardware/202309-32084/submission/360899/
"""

import argparse
import os
import pathlib
import tarfile
import tempfile

from requests import get

SESSION_ID = ""


def get_submissions_list(file):
    """
    Read the submission urls from a file line by line

    :param file: path to the file containing the submission URLs
    :return: a list of dictionaries with the submission information
    """

    # Read the submission urls from a file line by line
    with open(file, "r") as f:
        # Read the lines, ignoring the new line character
        lines = f.read().splitlines()

    submissions = []
    for line in lines:
        # Ignore lines starting with #
        if line.startswith("#"):
            continue
        # Remove the trailing slash
        url = line.rstrip("/")
        # Get the submission ID
        id = url.split("/")[-1]
        # Get the device ID
        device_id = url.split("/")[-3]

        submissions.append({"id": id, "device_id": device_id, "url": url})

    return submissions


def download_submissions(submission, session_id):
    id = submission["id"]
    url = submission["url"]

    path = pathlib.Path(f"submissions/{id}")

    # Check if the session ID is set
    if not session_id:
        raise SystemExit("Session ID is required to download the submissions.")

    # Create the submissions folder if it does not exist
    if not path.exists():
        pathlib.Path("submissions").mkdir(parents=True, exist_ok=True)

    # Check if the submission already exists
    if os.path.exists(path):
        print(f"File already exists: {path}")
        return

    # Get the content of the URL
    tokens = {"sessionid": session_id}
    response = get(f"{url}/data", cookies=tokens)
    if response.status_code == 200:
        # Find if the authentication failed looking at the content for
        # the string "OpenID transaction in progress"
        if "OpenID transaction in progress" in response.text:
            print(response.text)
            raise SystemExit("Authentication failed.")
        print(f"Submission downloaded successfully: {id}")
    else:
        raise SystemExit("Failed to download the file.")

    # Write the content to a temporary file
    with tempfile.NamedTemporaryFile(suffix=".tar.gz") as file:
        file.write(response.content)

        # Decompress the file using the tarfile module
        with tarfile.open(file.name, "r") as tar:
            tar.extractall(path=path)


def main():
    parser = argparse.ArgumentParser(
        description="Download a list of submissions from C3."
    )
    parser.add_argument(
        "submissions_file",
        help="File containing the submission URLs",
    )
    parser.add_argument(
        "--session-id",
        help="Session ID to authenticate with the certification website. "
        "It can be obtained in the developer section of your profile in C3",
        default="",
    )
    args = parser.parse_args()

    submissions = get_submissions_list(args.submissions_file)
    for submission in submissions:
        download_submissions(submission, args.session_id)


if __name__ == "__main__":
    main()
