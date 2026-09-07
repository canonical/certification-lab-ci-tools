# Example of the data in the file
# Submission Report URL
# https://certification.canonical.com/hardware/202309-32084/submission/360899/
# https://certification.canonical.com/hardware/202310-32275/submission/360894/
# https://certification.canonical.com/hardware/202401-33353/submission/360849/
# https://certification.canonical.com/hardware/202309-32040/submission/360844/
# https://certification.canonical.com/hardware/202312-33291/submission/360841/

import argparse
import csv
import os
import pathlib

from download_submissions import download_submissions, get_submissions_list


def get_failing_services_post_reboot(submissions, test="post-warm-reboot"):
    """
    Get the failing services from the test output file

    :param submissions: list of submissions
    :param test: name of the test
    :return: list of failing services
    """

    # Create a list to store the failing services
    failing_services = []
    for submission in submissions:
        id = submission["id"]
        test_name = f"com.canonical.certification__power-management_{test}"
        path = pathlib.Path(f"submissions/{id}/test_output/{test_name}")

        # Check if the file exists
        if not os.path.exists(path):
            print(f"File {path} does not exist")
            continue

        # Read the content of the file and check the failing services
        with open(path, "r") as file:
            content = file.read()
            # Find the lines starting with "●"  and get the service name
            # Example:
            # ● casper-md5check.service loaded failed failed casper-md5check Verify Live ISO checksums
            for line in content.splitlines():
                if line.startswith("●"):
                    service_name = line.split()[1]

                    # dictionary to store the failing services
                    row = {
                        "device_id": submission["device_id"],
                        "submission_id": id,
                        "service": service_name,
                    }

                    failing_services.append(row)

        # Create a CSV file with the failing services
        with open(f"failing_services_{test}.csv", "w") as csv_file:
            fieldnames = ["device_id", "submission_id", "service"]

            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

            writer.writeheader()
            writer.writerows(failing_services)


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
    # Choose between post-warm-reboot and post-cold-reboot
    parser.add_argument(
        "--test",
        default="post-warm-reboot",
        help="Test to get the failing services",
        choices=["post-warm-reboot", "post-cold-reboot"],
    )

    args = parser.parse_args()

    submissions = get_submissions_list(args.submissions_file)
    for submission in submissions:
        download_submissions(submission, args.session_id)

    get_failing_services_post_reboot(submissions, args.test)


if __name__ == "__main__":
    main()
