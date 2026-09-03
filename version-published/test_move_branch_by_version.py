import unittest
from unittest.mock import call, patch

import move_branch_by_version


class TestMoveBetaBranch(unittest.TestCase):
    @patch("move_branch_by_version.get_revision_at_offset")
    @patch("move_branch_by_version.check_call")
    def test_main_happy(self, mock_check_call, mock_get_revision_at_offset):
        mock_get_revision_at_offset.return_value = "tag_hash + 3"

        move_branch_by_version.main(["/path/to/repo", "beta", "v1.1.0-dev3"])

        self.assertIn(
            call(["git", "reset", "--hard", "tag_hash + 3"], cwd="/path/to/repo"),
            mock_check_call.call_args_list,
        )

    def test_main_unhappy(self):
        with self.assertRaises(SystemExit):
            move_branch_by_version.main(["/path/to/repo", "beta", "v1.1.0"])
