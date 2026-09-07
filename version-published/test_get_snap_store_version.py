import unittest
from unittest.mock import patch

import get_snap_store_version


class TestSnapScript(unittest.TestCase):
    def setUp(self):
        self.mock_snap_info = {
            "channel-map": [
                {"channel": {"name": "stable"}, "version": "1.0.0-dev23"},
                {"channel": {"name": "beta"}, "version": "1.1.0-dev23"},
                {"channel": {"name": "edge"}, "version": "1.2.0-dev40"},
            ]
        }

    @patch("get_snap_store_version.get_snap_info_from_store")
    def test_get_latest_version_stable(self, mock_get_info):
        mock_get_info.return_value = self.mock_snap_info
        version = get_snap_store_version.get_latest_version(
            self.mock_snap_info, "stable"
        )
        self.assertEqual(version, "1.0.0-dev23")

    @patch("get_snap_store_version.get_snap_info_from_store")
    def test_get_latest_version_beta(self, mock_get_info):
        mock_get_info.return_value = self.mock_snap_info
        version = get_snap_store_version.get_latest_version(self.mock_snap_info, "beta")
        self.assertEqual(version, "1.1.0-dev23")

    @patch("get_snap_store_version.get_snap_info_from_store")
    def test_get_latest_version_edge(self, mock_get_info):
        mock_get_info.return_value = self.mock_snap_info
        version = get_snap_store_version.get_latest_version(self.mock_snap_info, "edge")
        self.assertEqual(version, "1.2.0-dev40")

    @patch("get_snap_store_version.get_snap_info_from_store")
    def test_get_latest_version_no_channel(self, mock_get_info):
        mock_get_info.return_value = self.mock_snap_info
        with self.assertRaises(SystemExit):
            _ = get_snap_store_version.get_latest_version(
                self.mock_snap_info, "nonexistent"
            )
