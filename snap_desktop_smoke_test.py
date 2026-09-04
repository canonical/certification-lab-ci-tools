#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2017 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.

import os
import shutil
import subprocess
import sys
import tempfile

"""
This program checks if checkbox-snappy can be snapped and whether "Smoke Tests"
test plan passes after installing that snap.
"""

REPO = "https://git.launchpad.net/checkbox-snappy"


def update_snapcraft():
    subprocess.run(["snapcraft", "update"])


class Snap:
    def __init__(self, repo, branch, dont_clean=False):
        self._repo = repo
        self._branch = branch
        self._dont_clean = dont_clean
        self._work_dir = ""
        self._start_dir = os.path.abspath(os.curdir)
        self._log = ""

    def __enter__(self):
        self._work_dir = tempfile.mkdtemp("-checkbox-snappy-" + self._branch)
        os.chdir(self._work_dir)
        return self

    def clone(self):
        if self._run_cmd(["git", "clone", "-b", self._branch, self._repo, "."]) != 0:
            raise Exception(
                f"Failed to git-clone. Repo: {self._repo}. Branch: {self._branch}"
            )
        print(f"cloned into {self._work_dir}")

    def snap(self):
        if self._run_cmd(["snapcraft"]) != 0:
            raise Exception("Failed to snap checkbox-snappy")
        # the last line in the log should contain "Snapped $SNAPNAME"
        self._snap_path = self._tail_log().split()[1]
        print(f"{self._snap_path} snapped.")

    def __exit__(self, exc_type, exc_value, traceback):
        if not self._dont_clean:
            shutil.rmtree(self._work_dir)
        os.chdir(self._start_dir)

    def _run_cmd(self, args):
        cp = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self._log += cp.stdout.decode(sys.stdout.encoding)
        if cp.returncode != 0:
            print(
                "Command `{}` failed with return code {}".format(
                    " ".join(args), cp.returncode
                ),
                file=sys.stderr,
            )
        return cp.returncode

    def _tail_log(self, n=1):
        return "\n".join(self._log.strip().split("\n")[-n:])

    def install(self):
        if (
            self._run_cmd(["sudo", "snap", "install", "--devmode", self._snap_path])
            != 0
        ):
            raise Exception("Failed to install checkbox-snappy")

    def smoke_test(self):
        if self._run_cmd(["checkbox-snappy.smoke-test"]) != 0:
            raise Exception("Smoke test failed")

    def submit_logs(self):
        with open("snap-smoke.log", "wt") as f:
            f.write(self._log)
        if self._log:
            self._run_cmd(["pastebinit", "snap-smoke.log"])
            # last line contains URL from pastebinit
            print(f"log: {self._tail_log()}")
        else:
            print("log: empty")


def main():
    if len(sys.argv) == 2:
        if sys.argv[1] in ["-h", "--help"]:
            print("Snaps checkbox-snappy, installs it, and runs smoke-tests.")
            print(f"Usage:\n\t{sys.argv[0]} [BRANCH_NAME]")
            print()
            print("If BRANCH_NAME is omitted, master is used")
            return 0
        branch = sys.argv[1]
    else:
        branch = "master"
    with Snap(REPO, branch) as snap:
        try:
            snap.clone()
            snap.snap()
            snap.install()
            snap.smoke_test()
        except Exception as exc:
            print(exc, file=sys.stderr)
            print("Last 10 lines of output:")
            print(snap._tail_log(10))
            return 1
        finally:
            snap.submit_logs()
    return 0


if __name__ == "__main__":
    main()
