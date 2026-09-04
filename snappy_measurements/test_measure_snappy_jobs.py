# Copyright (C) 2018 Canonical Ltd
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

import unittest
from unittest.mock import MagicMock

from measure_snappy_jobs import InfluxQueryWriter


class InfluxQueryWriterTests(unittest.TestCase):
    def test_no_results_no_prints(self):
        submission = {
            "results": [],
        }
        iqw = InfluxQueryWriter("", submission, 0)
        self.assertEqual(list(iqw.generate_sql_inserts()), [])

    def test_one_result_no_meta_infos(self):
        submission = {
            "results": [
                {
                    "id": "snap-install",
                    "duration": 0.5,
                }
            ],
        }
        with unittest.mock.patch("time.time", MagicMock(return_value=1)):
            iqw = InfluxQueryWriter("unknown", submission, 1)
            expected = (
                'INSERT snap_timing,project_name="unknown",'
                'job_name="snap-install",hw_id="unknown",'
                'os_kind="unknown",core_revision=0 elapsed=0.5 1000000000'
            )
            self.assertEqual(list(iqw.generate_sql_inserts()), [expected])

    def test_empty_suspension(self):
        iqw = InfluxQueryWriter("", dict(), 0)
        self.assertEqual(list(iqw.generate_sql_inserts()), [])

    def test_full_meta(self):
        submission = {
            "distribution": {"description": "Ubuntu"},
            "duration": 0.5,
            "id": "snap-install",
            "title": "checkbox-project",
            "results": [
                {"id": "snap-install", "duration": 1.5},
                {"id": "snap-remove", "duration": 2.5},
            ],
        }
        expected1 = (
            'INSERT snap_timing,project_name="checkbox-project",'
            'job_name="snap-install",hw_id="unknown",'
            'os_kind="Ubuntu",core_revision=0 elapsed=1.5 1000000000'
        )
        expected2 = (
            'INSERT snap_timing,project_name="checkbox-project",'
            'job_name="snap-remove",hw_id="unknown",'
            'os_kind="Ubuntu",core_revision=0 elapsed=2.5 1000000000'
        )
        with unittest.mock.patch("time.time", MagicMock(return_value=1)):
            iqw = InfluxQueryWriter("unknown", submission, 1)
            self.assertEqual(list(iqw.generate_sql_inserts()), [expected1, expected2])
