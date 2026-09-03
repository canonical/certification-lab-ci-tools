#!/usr/bin/env python3
# Copyright (C) 2018-2019 Canonical Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Written by:
#       Maciej Kisielewski <maciej.kisielewski@canonical.com>
import json
import os
import re
import subprocess

from collections import defaultdict
from datetime import datetime, timedelta

"""
Pull historical results from Jenkins for quick import to InfluxDB.

This script needs to be run on a machine that has access to the Jenkins server.
Which is 'yantok' probably.

At the end it will print bash invocations that need to be run from within the
'data' directory to push the results to Influx.
"""

PROJECTS = [
    "cert-caracalla-gpa-core-beta",
    "cert-caracalla-media-core-beta",
    "cert-caracalla-transport-core-beta",
    "cert-cm3-core-beta",
    "cert-dragonboard-core-beta",
    "cert-havasu-core-beta",
    "cert-rpi2-core-beta",
    "cert-rpi3-armhf-core-beta",
    "cert-stlouis-core-beta",
    "cert-stlouis-tpm2-core-beta",
    "cert-tampere-core-beta",
    "cert-tillamook-core-beta",
    "cert-vienna-ioter5-core-beta",
    "cert-caracalla-transport-checkbox-plano-edge",
]

JENKINS = "http://10.101.50.238:8080/"


class WgetError(Exception):
    pass


def wget(url, filename=None):
    # this is needed as no python-wget or requests on yantok
    # if filename is None return the wgotten file as string
    cmd = ["wget", "-q", "-O", filename or "-", url]
    try:
        out = subprocess.check_output(cmd)
        return out.decode("utf-8")
    except subprocess.CalledProcessError:
        raise WgetError


def get_latest_builds():
    url = JENKINS + "job/{job_name}/api/json"
    builds = dict()
    for proj in PROJECTS:
        try:
            res = wget(url.format(job_name=proj))
        except WgetError:
            print(
                'Unable to fetch "{}" jenkins project information. '
                "Is the project still available?".format(proj)
            )
            continue
        job_desc = json.loads(res)
        try:
            builds[proj] = job_desc["lastBuild"]["number"]
        except KeyError:
            print("failed to get last build number for {}".format(proj))
    return builds


def pull(proj, index):
    print("pulling artifacts of job #{} for {}".format(index, proj))
    base_url = JENKINS + "view/Core/job/{}/{}/".format(proj, index)
    snap_url = base_url + "artifact/artifacts/snaplist.txt/*view*/"
    console_url = base_url + "consoleText"
    submission_url = base_url + "artifact/artifacts/submission.json/*view*/"
    try:
        wget(console_url, "meta")
        wget(submission_url, "submission.json")
        wget(snap_url, "snaplist")
    except WgetError:
        return False
    return True


def download_artifacts(projects):
    # this is file-system stateful so it's easier to debug/reuse
    latest_good = dict()
    for proj in projects.keys():
        os.makedirs(proj, exist_ok=True)
        os.chdir(proj)
        # let's create a copy so we can modify original while iterating
        builds = projects[proj][:]
        for index in builds:
            if os.path.exists(str(index)):
                print("{}/{} already exists. Skipping.".format(proj, index))
                continue
            os.mkdir(str(index))
            os.chdir(str(index))
            try:
                pull(proj, index)
                os.chdir("..")
            except WgetError:
                os.chdir("..")
                shutil.rmtree(str(index), ignore_errors=True)
                proj.remove(index)
                shutil.rmtree(str(index), ignore_errors=True)
        os.chdir("..")


def extract_timestamp(path):
    dt = None
    with open(os.path.join(path, "meta"), "rt") as f:
        for line in f.readlines():
            regex = re.compile(r"\d{4}-\d{2}-\d{2}\ \d{2}:\d{2}:\d{2}")
            match = regex.match(line)
            if match:
                dt = datetime.strptime(match.group(), "%Y-%m-%d %H:%M:%S")
                break
    return dt


def measurement_tool_invocation(projects):
    for proj in projects.keys():
        for index in projects[proj]:
            val = extract_timestamp(os.path.join(proj, str(index)))
            if val:
                timestamp = (val - datetime(1970, 1, 1)) / timedelta(seconds=1)
                cmd = [
                    "../measure_snappy_jobs.py",
                    "--hw_id",
                    proj,
                    "--timestamp",
                    str(timestamp),
                    os.path.join(proj, str(index), "submission.json"),
                ]
                # XXX: This could call the measure_snapp_jobs.py directly
                #      but the whole script would need an access to both:
                #      Jenkins and InfluxDB
                print(" ".join(cmd))


def push_results(projects):
    from measure_snappy_jobs import InfluxQueryWriter, push_to_influx

    problems = []
    for proj in projects.keys():
        for index in projects[proj]:
            val = extract_timestamp(os.path.join(proj, str(index)))
            if val:
                timestamp = (val - datetime(1970, 1, 1)) / timedelta(seconds=1)
                submission_file = os.path.join(proj, str(index), "submission.json")
                with open(submission_file, "rt", encoding="utf-8") as f:
                    try:
                        content = json.load(f)
                    except json.JSONDecodeError:
                        print("Failed to parse {}".format(submission_file))
                        continue
                    iqw = InfluxQueryWriter(proj, content, timestamp)
                    res = push_to_influx(iqw.extract_measurements())
    return problems


def main():
    try:
        with open("previous_pulls.json", "rt", encoding="utf-8") as f:
            prev = json.loads(f.read())
    except:
        print("Unable to read previous_pulls.json. Downloading everything!")
        prev = dict()
    prev = defaultdict(int, prev)
    last_builds = get_latest_builds()
    projects = {
        n: list(range(prev[n] + 1, last_builds[n] + 1)) for n in last_builds.keys()
    }
    start_dir = os.path.abspath(os.curdir)
    os.makedirs("data", exist_ok=True)
    os.chdir("data")
    download_artifacts(projects)
    problems = push_results(projects)
    for proj, builds in projects.items():
        if builds:
            last_builds[proj] = builds[-1]
    os.chdir(start_dir)
    with open("previous_pulls.json", "wt", encoding="utf-8") as f:
        f.write(json.dumps(last_builds, indent=4, sort_keys=True))
    if problems:
        print("\n".join(problems))
        raise SystemExit("There were problems. See logs")


if __name__ == "__main__":
    main()
