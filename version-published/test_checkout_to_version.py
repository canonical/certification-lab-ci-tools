import unittest
import subprocess
from unittest.mock import patch

import checkout_to_version


class TestCheckoutToVersion(unittest.TestCase):
    @patch("checkout_to_version.check_call")
    @patch("checkout_to_version.get_revision_at_offset")
    def test_main_happy(self, get_revision_at_offset_mock, check_call_mock):
        checkout_to_version.main(["checkbox", "v1.2.3-dev1"])
        self.assertTrue(get_revision_at_offset_mock.called)
        self.assertTrue(check_call_mock.called)

    @patch("checkout_to_version.check_call")
    @patch("checkout_to_version.get_revision_at_offset")
    def test_main_unhappy(self, get_revision_at_offset_mock, check_call_mock):
        check_call_mock.side_effect = subprocess.CalledProcessError(1, "cmd")

        with self.assertRaises(subprocess.CalledProcessError):
            checkout_to_version.main(["checkbox", "v1.2.3-dev1"])

        self.assertTrue(get_revision_at_offset_mock.called)
        self.assertTrue(check_call_mock.called)
