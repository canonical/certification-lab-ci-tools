#!/usr/bin/env python3
# Copyright (c) 2019 Canonical Ltd.
#
# Authors:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import json
import os
import time
from collections import defaultdict
from datetime import date, datetime, timedelta

import pytz
import requests
from launchpadlib.launchpad import Launchpad

ALL_STATUSES = [
    "Fix Committed",
    "Invalid",
    "Won't Fix",
    "Confirmed",
    "Triaged",
    "Expired",
    "In Progress",
    "Incomplete",
    "Fix Released",
    "New",
    "Opinion",
]


class StatHarvester:
    def __init__(self, project):
        self.proj = project
        self.changes = defaultdict(lambda: {key: 0 for key in ALL_STATUSES})
        self.till_fixed = []
        self.till_released = []
        last_stats = self.load_last_stats()
        self.since = last_stats["date"] + timedelta(seconds=1)
        self.bugs_timeline = {last_stats["date"].date(): last_stats["stats"]}
        # we want to compute the stats for up to the previous day
        # to do that we need a datetime for the last second of the day
        # this is the most right way to do it, as there are leap seconds
        # and other insanities
        t = datetime.today()
        self.until = datetime(t.year, t.month, t.day, tzinfo=pytz.utc) - timedelta(
            seconds=1
        )

    def harvest(self):
        if self.since > self.until:
            print("Stats already harvested for up to yesterday")
            raise SystemExit()

        launchpad = Launchpad.login_with(
            "stats-harvester", "production", credentials_file="./lp_credentials"
        )
        print(f"Searching for '{self.proj}' bugs modified since {self.since}")
        modified_bugs = launchpad.projects[self.proj].searchTasks(
            status=ALL_STATUSES, modified_since=self.since
        )
        time_left_str = "unknown"
        start_time = time.time()
        for i, bug in enumerate(modified_bugs, 1):
            print(
                f"Processing bug {i}/{len(modified_bugs)}. Estimated time to complete {time_left_str}"
            )
            self._process_bug(bug)
            cur_time = time.time()
            estimated_total = (cur_time - start_time) * len(modified_bugs) / i
            estimated_time_left = max(0, start_time + estimated_total - cur_time)
            time_left_str = f"{estimated_time_left:.2f}s"
        self.generate_timeline()

    def generate_timeline(self):
        date_cursor = self.since.date()
        previous_stats = self.bugs_timeline.get(
            date_cursor - timedelta(days=1), {key: 0 for key in ALL_STATUSES}
        )
        while date_cursor < date.today():
            self.bugs_timeline[date_cursor] = previous_stats.copy()
            for key in ALL_STATUSES:
                self.bugs_timeline[date_cursor][key] += self.changes[date_cursor][key]
            previous_stats = self.bugs_timeline[date_cursor]
            date_cursor += timedelta(1)

    def generate_records(self):
        results = []
        influx_friendly_statuses = {
            "Confirmed": "confirmed",
            "Fix Committed": "fixcommitted",
            "Fix Released": "fixreleased",
            "In Progress": "inprogress",
            "Incomplete": "incomplete",
            "Invalid": "invalid",
            "New": "new",
            "Opinion": "opinion",
            "Triaged": "triaged",
            "Won't Fix": "wontfix",
            "Expired": "expired",
        }
        for date_ in sorted(self.bugs_timeline):
            for status in sorted(self.bugs_timeline[date_]):
                result = {
                    "time": int(date_.strftime("%s")) * 10**9,
                    "status": influx_friendly_statuses[status],
                    "count": self.bugs_timeline[date_][status],
                }
                results.append(result)
        return results

    def dump_json(self):
        with open(self._generate_filename("time_till_fixed"), "wt") as f:
            json.dump(self.till_fixed, f, indent=2)
        with open(self._generate_filename("time_till_released"), "wt") as f:
            json.dump(self.till_released, f, indent=2)
        with open(self._generate_filename("bugs_statistics"), "wt") as f:
            json.dump(self.generate_records(), f, indent=2)

    def dump_sql(self):
        for res in self.generate_records():
            print(
                "insert {},project={},tags=all value={}i {}".format(
                    "launchpad_bugs_{}".format(res["status"]),
                    self.proj,
                    res["count"],
                    res["time"],
                )
            )

    def push_to_bork(self, bork_addr, db_name):
        measurements = []
        for res in self.generate_records():
            point = {
                "measurement": "launchpad_bugs_{}".format(res["status"]),
                "tags": {
                    "tags": "all",
                    "project": self.proj,
                },
                "fields": {
                    "value": res["count"],
                },
                "time": res["time"],
            }
            measurements.append(point)
        for res in self.till_fixed:
            point = {
                "measurement": "time_to_fix_committed",
                "tags": {
                    "tags": res["tags"],
                    "project": self.proj,
                    "id": res["id"],
                },
                "fields": {
                    "hours": res["hours"],
                },
                "time": res["time"],
            }
            measurements.append(point)
        for res in self.till_released:
            point = {
                "measurement": "time_to_fix_released",
                "tags": {
                    "tags": res["tags"],
                    "project": self.proj,
                    "id": res["id"],
                },
                "fields": {
                    "hours": res["hours"],
                },
                "time": res["time"],
            }
            measurements.append(point)

        bork_url = f"http://{bork_addr}/influx"
        # infrastructure can choke on too big bundle of records,
        # so let's chop it into 1000-record-long chunks
        while measurements:
            chunk = measurements[:1000]
            measurements = measurements[100:]
            request = {
                "database": db_name,
                "measurements": chunk,
            }
            response = requests.post(bork_url, json=request)
            if not response:
                print(
                    f"Couldn't push measurements:\n{response}: {response.text}"
                )

    def dump_last_stats(self):
        last_state = {
            "date": self.until.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "stats": self.bugs_timeline[self.until.date()],
        }
        with open(f"{self.proj}-last-stats.json", "wt") as f:
            json.dump(last_state, f, indent=2)

    def load_last_stats(self):
        try:
            with open(f"{self.proj}-last-stats.json", "rt") as f:
                stats = json.load(f)
            stats["date"] = datetime.strptime(stats["date"], "%Y-%m-%dT%H:%M:%S%z")
            return stats
        except Exception as exc:
            print("Problem with parsing the date from last-stats")
            print(exc)
            return {
                "date": datetime(2012, 8, 1, tzinfo=pytz.utc),
                "stats": {key: 0 for key in ALL_STATUSES},
            }

    def _generate_filename(self, name):
        basename = "{}-{}-{}".format(
            self.proj,
            name,
            datetime.today().strftime("%Y-%m-%d"),
            self.until.strftime("%Y-%m-%d"),
        )
        possible_name = basename + ".json"
        if os.path.exists(possible_name):
            for i in range(1, 1000):
                possible_name = f"{basename}({i}).json"
                if not os.path.exists(possible_name):
                    return possible_name
        else:
            return possible_name
        raise SystemExit("There's too many dumps from today!")

    def _process_bug(self, bug):
        bug_date = bug.date_created.date()
        # bugs can be filed with any given status, so we cannot just write down
        # 'New' += 1
        # if the first status change is from status other than 'New' it means
        # that the bug was filed with a different one, let's correct that on
        # the first status change encounter
        seen_first_change = False
        for act in bug.bug.activity:
            if act.whatchanged == f"{self.proj}: status":
                if not seen_first_change:
                    born_status = act.oldvalue
                    seen_first_change = True
                if act.datechanged < self.since or act.datechanged > self.until:
                    continue
                date = act.datechanged.date()
                self.changes[date][act.oldvalue] -= 1
                self.changes[date][act.newvalue] += 1
        # find time to it took from confirmed to fixed
        if bug.date_fix_committed:
            date_confirmed = bug.date_confirmed or bug.date_triaged or bug.date_created
            ttfc = bug.date_fix_committed - date_confirmed
            self.till_fixed.append(
                {
                    "hours": ttfc.total_seconds() // 3600,
                    "time": int(bug.date_fix_committed.date().strftime("%s")) * 10**9,
                    "project": self.proj,
                    "id": bug.bug.id,
                    "tags": " ".join(bug.bug.tags),
                }
            )
        if bug.date_fix_released:
            date_confirmed = bug.date_confirmed or bug.date_triaged or bug.date_created
            ttfr = bug.date_fix_released - date_confirmed
            self.till_released.append(
                {
                    "hours": ttfr.total_seconds() // 3600,
                    "time": int(bug.date_fix_released.date().strftime("%s")) * 10**9,
                    "project": self.proj,
                    "id": bug.bug.id,
                    "tags": " ".join(bug.bug.tags),
                }
            )
        # if we still haven't seen a status changes it means that the bug has
        # the same status it was filed with
        if not seen_first_change:
            born_status = bug.status
        # now we know the real status the bug was filed with, let's write it
        # down
        self.changes[bug_date][born_status] += 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("--db-bridge", help="IP address of the db-bridge to use")
    parser.add_argument(
        "--dump-json", help="Dump statistics to JSON files", action="store_true"
    )
    parser.add_argument("--db-name", help="Database name to push results to")

    args = parser.parse_args()
    harvester = StatHarvester(args.project)
    harvester.harvest()
    harvester.dump_last_stats()
    if args.dump_json:
        harvester.dump_json()
    if args.db_bridge:
        if not args.db_name:
            raise SystemExit("You need to provide --db-name when using bork!")
        harvester.push_to_bork(args.db_bridge, args.db_name)


if __name__ == "__main__":
    main()
