import textwrap
import unittest
from unittest.mock import MagicMock, patch

import snap_info_utility


class TestSnapInfoUtility(unittest.TestCase):
    def test_get_version_and_offset(self):
        version = "v1.2.3-dev45"
        b_version, offset = snap_info_utility.get_version_and_offset(version)
        self.assertEqual(b_version, "1.2.3")
        self.assertEqual(offset, 45)

        version = "1.2.3"
        b_version, offset = snap_info_utility.get_version_and_offset(version)
        self.assertEqual(b_version, "1.2.3")
        self.assertEqual(offset, 0)

        version = "1.2.3.dev45"
        b_version, offset = snap_info_utility.get_version_and_offset(version)
        self.assertEqual(b_version, "1.2.3")
        self.assertEqual(offset, 45)

        version = "v1.2"
        b_version, offset = snap_info_utility.get_version_and_offset(version)
        self.assertEqual(b_version, "1.2")
        self.assertEqual(offset, 0)

        version = "bad.version.devbad"
        with self.assertRaises(SystemExit):
            snap_info_utility.get_version_and_offset(version)

    @patch("snap_info_utility.check_output")
    def test_get_list_of_tags(self, mock_check_output):
        mock_check_output.return_value = textwrap.dedent(
            """
            v1.2.3
            v1.2.2
            v1.2.1
            """
        )
        result = snap_info_utility.get_list_of_tags("/path/to/repo")
        self.assertEqual(result, ["v1.2.3", "v1.2.2", "v1.2.1"])

    @patch("snap_info_utility.check_output")
    def test_get_list_of_tags_error(self, mock_check_output):
        mock_check_output.return_value = ""
        with self.assertRaises(SystemExit):
            snap_info_utility.get_list_of_tags("/path/to/repo")

    @patch("snap_info_utility.check_output")
    def test_get_previous_tag(self, mock_check_output):
        tags = ["v1.2.3", "v1.2.2", "v1.2.1"]
        result = snap_info_utility.get_previous_tag("1.2.3", tags)
        self.assertEqual(result, "v1.2.2")

    @patch("snap_info_utility.get_list_of_tags", MagicMock())
    @patch("snap_info_utility.get_previous_tag")
    @patch("snap_info_utility.get_history_since")
    def test_get_revision_at_offset(
        self, mock_get_history_since, mock_get_previous_tag
    ):
        mock_get_previous_tag.return_value = "v1.0.0"
        mock_get_history_since.return_value = [
            "tag_hash + 3",
            "tag_hash + 2",
            "tag_hash + 1",
            "tag_hash",
        ]

        result = snap_info_utility.get_revision_at_offset(
            "v1.2.3-dev2", "/path/to/repo"
        )

        self.assertEqual(result, "tag_hash + 2")

    @patch("snap_info_utility.get_list_of_tags", MagicMock())
    @patch("snap_info_utility.get_previous_tag")
    @patch("snap_info_utility.get_history_since")
    def test_get_revision_at_offset_error(
        self, mock_get_history_since, mock_get_previous_tag
    ):
        mock_get_previous_tag.return_value = "v1.0.0"
        mock_get_history_since.return_value = [
            "tag_hash + 3",
            "tag_hash + 2",
            "tag_hash + 1",
            "tag_hash",
        ]

        with self.assertRaises(SystemExit):
            snap_info_utility.get_revision_at_offset("v1.2.3-dev5", "/path/to/repo")
