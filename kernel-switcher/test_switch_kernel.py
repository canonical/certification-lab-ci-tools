# Copyright (C) 2023 Canonical Ltd
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

import argparse
import unittest
from unittest.mock import call, mock_open, patch

from switch_kernel import (
    add_efi_opt,
    assert_root,
    find_menuentry_for_kernel,
    get_grub_cfg_contents,
    get_grub_default_contents,
    get_submenu_entry,
    main,
    parse_args,
    update_cmd_linux,
    update_grub_default_contents,
)


class TestAssertRoot(unittest.TestCase):
    @patch("os.geteuid")
    def test_root_user(self, mock_geteuid):
        """Test behavior when the user is root."""
        mock_geteuid.return_value = 0

        try:
            assert_root()
        except SystemExit:
            self.fail("assert_root() raised SystemExit unexpectedly!")

    @patch("os.geteuid")
    def test_non_root_user(self, mock_geteuid):
        """Check if program exits with an error when the EUID is 1001."""
        mock_geteuid.return_value = 1001

        with self.assertRaises(SystemExit) as context:
            assert_root()

        self.assertEqual(str(context.exception), "This program must be run as root.")


class TestFindMenuentryForKernel(unittest.TestCase):
    def test_find_correct_menuentry(self):
        grub_entry = (
            "menuentry 'Ubuntu, with Linux 5.4.0-80-generic' --class ubuntu "
            "--class gnu-linux --class gnu --class os $menuentry_id_option "
            "'gnulinux-5.4.0-80-generic-advanced-aca31037-7571-415c-b666-"
            "f565c524c2a6' {"
        )
        correct_match = (
            "gnulinux-5.4.0-80-generic-advanced-aca31037-7571-415c-b666-f565c524c2a6"
        )

        match = find_menuentry_for_kernel("5.4.0-80", grub_entry)
        self.assertEqual(match, correct_match)

    def test_raises_system_exit_for_no_menuentry(self):
        with self.assertRaises(SystemExit) as context:
            find_menuentry_for_kernel("5.4.0-80", "foo")

        self.assertEqual(str(context.exception), "Could not find kernel in grub.cfg")

    def test_keyword_at_different_positions(self):
        grub_entry = (
            "menuentry 'with Linux Ubuntu, 5.4.0-80-generic' --class ubuntu "
            "--class gnu-linux --class gnu --class os $menuentry_id_option "
            "'gnulinux-5.4.0-80-generic-advanced-aca31037-7571-415c-b666-"
            "f565c524c2a6' {"
        )
        correct_match = (
            "gnulinux-5.4.0-80-generic-advanced-aca31037-7571-415c-b666-f565c524c2a6"
        )
        match = find_menuentry_for_kernel("5.4.0-80", grub_entry)
        self.assertEqual(match, correct_match)

    def test_avoid_recovery(self):
        grub_entry = (
            "menuentry 'with Linux Ubuntu, 5.4.0-80-generic-recovery' "
            "--class ubuntu --class gnu-linux --class gnu --class os "
            "$menuentry_id_option 'gnulinux-recovery-5.4.0-80-generic-"
            "advanced-aca31037-7571-415c-b666-f565c524c2a6' {"
        )
        with self.assertRaises(SystemExit) as context:
            find_menuentry_for_kernel("5.4.0-80", grub_entry)
        self.assertEqual(str(context.exception), "Could not find kernel in grub.cfg")

    def test_multiple_matches(self):
        grub_entries = (
            "menuentry 'Ubuntu, with Linux 5.4.0-80-generic' --class ubuntu "
            "--class gnu-linux --class gnu --class os $menuentry_id_option "
            "'gnulinux-5.4.0-80-generic-advanced-first' {"
            "\n"
            "menuentry 'Ubuntu, with Linux 5.4.0-80-generic' --class ubuntu "
            "--class gnu-linux --class gnu --class os $menuentry_id_option "
            "'gnulinux-5.4.0-80-generic-advanced-second' {"
        )
        match = find_menuentry_for_kernel("5.4.0-80", grub_entries)
        self.assertEqual(match, "gnulinux-5.4.0-80-generic-advanced-first")

    def test_no_menuentry_keyword(self):
        grub_entry = (
            "'Ubuntu, with Linux 5.4.0-80-generic' --class ubuntu "
            "--class gnu-linux --class gnu --class os $changed_id_option "
            "'gnulinux-5.4.0-80-generic-advanced-aca31037-7571-415c-b666-"
            "f565c524c2a6' {"
        )
        with self.assertRaises(SystemExit) as context:
            find_menuentry_for_kernel("5.4.0-80", grub_entry)
        self.assertEqual(str(context.exception), "Could not find kernel in grub.cfg")

    def test_empty_input(self):
        with self.assertRaises(SystemExit) as context:
            find_menuentry_for_kernel("", "")
        self.assertEqual(str(context.exception), "Could not find kernel in grub.cfg")


class TestGetSubmenuEntry(unittest.TestCase):
    def test_valid_submenu_entry(self):
        grub_entry = (
            "submenu 'Advanced options for Ubuntu' $menuentry_id_option "
            "'gnulinux-advanced-aca31037-7571-415c-b666-f565c524c2a6' {"
        )
        expected = "gnulinux-advanced-aca31037-7571-415c-b666-f565c524c2a6"
        result = get_submenu_entry(grub_entry)
        self.assertEqual(result, expected)

    def test_no_submenu_entry(self):
        with self.assertRaises(SystemExit) as context:
            get_submenu_entry("foo")
        self.assertEqual(
            str(context.exception), "Could not find submenu entry in grub.cfg"
        )

    # Additional tests:

    def test_submenu_without_advanced(self):
        grub_entry = (
            "submenu 'Options for Ubuntu' $menuentry_id_option "
            "'gnulinux-options-aca31037-7571-415c-b666-f565c524c2a6' {"
        )

        with self.assertRaises(SystemExit) as context:
            get_submenu_entry("foo")
        self.assertEqual(
            str(context.exception), "Could not find submenu entry in grub.cfg"
        )

    def test_multiple_submenu_entries(self):
        grub_entries = (
            "submenu 'Options for Linux' $menuentry_id_option "
            "'gnulinux-1' {"
            "\n"
            "submenu 'Advanced options for Ubuntu' $menuentry_id_option "
            "'gnulinux-advanced-aca31037-7571-415c-b666-f565c524c2a6' {"
        )
        expected = "gnulinux-advanced-aca31037-7571-415c-b666-f565c524c2a6"
        result = get_submenu_entry(grub_entries)
        self.assertEqual(result, expected)

    def test_invalid_submenu_format(self):
        grub_entry = "submenu 'Options for Ubuntu'"
        with self.assertRaises(SystemExit) as context:
            get_submenu_entry(grub_entry)
        self.assertEqual(
            str(context.exception), "Could not find submenu entry in grub.cfg"
        )

    def test_empty_input(self):
        with self.assertRaises(SystemExit) as context:
            get_submenu_entry("")
        self.assertEqual(
            str(context.exception), "Could not find submenu entry in grub.cfg"
        )


class TestGetGrubCfgContents(unittest.TestCase):
    @patch("builtins.open", new_callable=mock_open, read_data="test data")
    def test_returns_contents_of_grub_cfg(self, mock_file):
        contents = get_grub_cfg_contents()
        mock_file.assert_called_once_with("/boot/grub/grub.cfg", "rt")
        self.assertEqual(contents, "test data")

    @patch("builtins.open", side_effect=OSError("file not found"))
    def test_raises_system_exit_if_file_not_found(self, mock_file):
        with self.assertRaises(SystemExit) as context:
            get_grub_cfg_contents()
        self.assertEqual(
            str(context.exception),
            "Could not read /boot/grub/grub.cfg: file not found",
        )


class TestGetGrubDefaultContents(unittest.TestCase):
    @patch("builtins.open", new_callable=mock_open, read_data="test data")
    def test_returns_contents_of_grub_default(self, mock_file):
        contents = get_grub_default_contents()
        mock_file.assert_called_once_with("/etc/default/grub", "rt")
        self.assertEqual(contents, "test data")

    @patch("builtins.open", side_effect=OSError("file not found"))
    def test_raises_system_exit_if_file_not_found(self, mock_file):
        with self.assertRaises(SystemExit) as context:
            get_grub_default_contents()
        self.assertEqual(
            str(context.exception),
            "Could not read /etc/default/grub: file not found",
        )


class TestUpdateGrubDefaultContents(unittest.TestCase):
    @patch("builtins.open", new_callable=mock_open)
    @patch("subprocess.run")
    def test_writes_and_updates_grub(self, mock_run, mock_file):
        new_contents = "GRUB_DEFAULT=0\nGRUB_TIMEOUT=5\n"
        update_grub_default_contents(new_contents)
        mock_file.assert_called_once_with("/etc/default/grub", "wt")
        mock_file().write.assert_called_once_with(new_contents)
        mock_run.assert_called_once_with(["update-grub"])

    @patch("builtins.open", side_effect=OSError("file not found"))
    def test_raises_system_exit_if_file_not_found(self, mock_file):
        with self.assertRaises(SystemExit) as context:
            update_grub_default_contents("GRUB_DEFAULT=0\nGRUB_TIMEOUT=5\n")
        self.assertEqual(
            str(context.exception),
            "Could not write /etc/default/grub: file not found",
        )


class TestParseArgs(unittest.TestCase):
    def test_parse_args(self):
        argv = ["switch_kernel.py", "5.4.0-80"]
        args = parse_args(argv)
        self.assertEqual(args.kernel[0], "5.4.0-80")
        self.assertFalse(args.dry_run)
        self.assertFalse(args.enable_efi_vars)

    def test_parse_args_with_dry_run(self):
        argv = ["switch_kernel.py", "5.4.0-80", "--dry-run"]
        args = parse_args(argv)
        self.assertEqual(args.kernel[0], "5.4.0-80")
        self.assertTrue(args.dry_run)
        self.assertFalse(args.enable_efi_vars)

    def test_parse_args_with_efi_vars(self):
        argv = ["switch_kernel.py", "5.4.0-80", "--enable-efi-vars"]
        args = parse_args(argv)
        self.assertEqual(args.kernel[0], "5.4.0-80")
        self.assertFalse(args.dry_run)
        self.assertTrue(args.enable_efi_vars)


class TestAddEfiOpt(unittest.TestCase):
    def test_add_efi_opt_replace_noruntime(self):
        before = "efi=noruntime"
        self.assertEqual(add_efi_opt(before), "efi=runtime")

    def test_add_efi_opt_empty(self):
        self.assertEqual(add_efi_opt(""), "efi=runtime")

    def test_add_efi_opt_no_change(self):
        self.assertEqual(add_efi_opt("efi=runtime"), "efi=runtime")

    def test_add_efi_opt_add_runtime(self):
        before = "quiet splash"
        self.assertEqual(add_efi_opt(before), "quiet splash efi=runtime")

    def test_add_efi_opt_replace_in_the_middle(self):
        before = "quiet efi=noruntime splash"
        self.assertEqual(add_efi_opt(before), "quiet efi=runtime splash")


class TestUpdateCmdLinux(unittest.TestCase):
    def test_update_cmd_linux_smoke(self):
        before = 'FOO=bar\nGRUB_CMDLINE_LINUX="quiet splash"\nBIZ=baz'
        after = 'FOO=bar\nGRUB_CMDLINE_LINUX="quiet splash efi=runtime"\nBIZ=baz'
        self.assertEqual(update_cmd_linux(before), after)

    def test_update_cmd_linux_empty(self):
        before = ""
        after = ""
        self.assertEqual(update_cmd_linux(before), after)


class TestMain(unittest.TestCase):
    @patch("switch_kernel.parse_args")
    @patch("switch_kernel.get_grub_cfg_contents")
    @patch("switch_kernel.get_submenu_entry")
    @patch("switch_kernel.find_menuentry_for_kernel")
    @patch("switch_kernel.get_grub_default_contents")
    @patch("switch_kernel.update_grub_default_contents")
    @patch("builtins.print")
    @patch("os.path.exists")
    @patch("os.remove")
    def test_main(
        self,
        mock_remove,
        mock_exists,
        mock_print,
        mock_update_grub_default_contents,
        mock_get_grub_default_contents,
        mock_find_menuentry_for_kernel,
        mock_get_submenu_entry,
        mock_get_grub_cfg_contents,
        mock_parse_args,
    ):
        # Set up mocks
        mock_parse_args.return_value = argparse.Namespace(
            kernel=["5.4.0-80"], dry_run=False, enable_efi_vars=False
        )
        mock_get_grub_cfg_contents.return_value = "test grub cfg contents"
        mock_get_submenu_entry.return_value = "test submenu entry"
        mock_find_menuentry_for_kernel.return_value = "test menuentry"
        mock_get_grub_default_contents.return_value = (
            "GRUB_DEFAULT=test grub default contents"
        )
        mock_exists.return_value = True

        # Call main
        main([])

        # Check that the expected functions were called with the expected arguments
        mock_parse_args.assert_called_once_with([])
        mock_get_grub_cfg_contents.assert_called_once_with()
        mock_get_submenu_entry.assert_called_once_with("test grub cfg contents")
        mock_find_menuentry_for_kernel.assert_called_once_with(
            "5.4.0-80", "test grub cfg contents"
        )
        mock_get_grub_default_contents.assert_called_once_with()
        mock_remove.assert_called_once_with("/etc/default/grub.d/40-force-partuuid.cfg")
        mock_update_grub_default_contents.assert_called_once_with(
            "GRUB_DEFAULT='test submenu entry>test menuentry'"
        )

        # Check that the expected output was printed
        mock_print.assert_has_calls(
            [
                call("Reading existing kernel from /boot/grub/grub.cfg..."),
                call("Found submenu entry: test submenu entry"),
                call("Searching for menuentry for kernel 5.4.0-80..."),
                call("Found menuentry: test menuentry"),
                call("Removing 'force partuuid' from grub config..."),
                call("Setting new default: test submenu entry>test menuentry"),
            ]
        )

    @patch("switch_kernel.parse_args")
    @patch("switch_kernel.get_grub_cfg_contents")
    @patch("switch_kernel.get_submenu_entry")
    @patch("switch_kernel.find_menuentry_for_kernel")
    @patch("switch_kernel.get_grub_default_contents")
    @patch("switch_kernel.update_grub_default_contents")
    @patch("builtins.print")
    @patch("os.path.exists")
    @patch("os.remove")
    def test_main_no_partuuid(
        self,
        mock_remove,
        mock_exists,
        mock_print,
        mock_update_grub_default_contents,
        mock_get_grub_default_contents,
        mock_find_menuentry_for_kernel,
        mock_get_submenu_entry,
        mock_get_grub_cfg_contents,
        mock_parse_args,
    ):
        # Set up mocks
        mock_parse_args.return_value = argparse.Namespace(
            kernel=["5.4.0-80"], dry_run=False, enable_efi_vars=False
        )
        mock_get_grub_cfg_contents.return_value = "test grub cfg contents"
        mock_get_submenu_entry.return_value = "test submenu entry"
        mock_find_menuentry_for_kernel.return_value = "test menuentry"
        mock_get_grub_default_contents.return_value = (
            "GRUB_DEFAULT=test grub default contents"
        )
        mock_exists.return_value = False

        # Call main
        main([])

        # Check that the expected functions were called with the expected arguments
        mock_parse_args.assert_called_once_with([])
        mock_get_grub_cfg_contents.assert_called_once_with()
        mock_get_submenu_entry.assert_called_once_with("test grub cfg contents")
        mock_find_menuentry_for_kernel.assert_called_once_with(
            "5.4.0-80", "test grub cfg contents"
        )
        mock_get_grub_default_contents.assert_called_once_with()
        mock_remove.assert_not_called()
        mock_update_grub_default_contents.assert_called_once_with(
            "GRUB_DEFAULT='test submenu entry>test menuentry'"
        )

        # Check that the expected output was printed
        mock_print.assert_has_calls(
            [
                call("Reading existing kernel from /boot/grub/grub.cfg..."),
                call("Found submenu entry: test submenu entry"),
                call("Searching for menuentry for kernel 5.4.0-80..."),
                call("Found menuentry: test menuentry"),
                call("Removing 'force partuuid' from grub config..."),
                call("partuuid.cfg not found, not removing."),
                call("Setting new default: test submenu entry>test menuentry"),
            ]
        )

    @patch("switch_kernel.parse_args")
    @patch("switch_kernel.get_grub_cfg_contents")
    @patch("switch_kernel.get_submenu_entry")
    @patch("switch_kernel.find_menuentry_for_kernel")
    @patch("switch_kernel.get_grub_default_contents")
    @patch("switch_kernel.update_grub_default_contents")
    @patch("builtins.print")
    @patch("os.path.exists")
    @patch("os.remove")
    def test_main_dry_run(
        self,
        mock_remove,
        mock_exists,
        mock_print,
        mock_update_grub_default_contents,
        mock_get_grub_default_contents,
        mock_find_menuentry_for_kernel,
        mock_get_submenu_entry,
        mock_get_grub_cfg_contents,
        mock_parse_args,
    ):
        # Set up mocks
        mock_parse_args.return_value = argparse.Namespace(
            kernel=["5.4.0-80"], dry_run=True, enable_efi_vars=False
        )
        mock_get_grub_cfg_contents.return_value = "test grub cfg contents"
        mock_get_submenu_entry.return_value = "test submenu entry"
        mock_find_menuentry_for_kernel.return_value = "test menuentry"
        mock_get_grub_default_contents.return_value = (
            "GRUB_DEFAULT=test grub default contents"
        )

        # Call main
        main([])

        # Check that the expected functions were called with the expected arguments
        mock_parse_args.assert_called_once_with([])
        mock_get_grub_cfg_contents.assert_called_once_with()
        mock_get_submenu_entry.assert_called_once_with("test grub cfg contents")
        mock_find_menuentry_for_kernel.assert_called_once_with(
            "5.4.0-80", "test grub cfg contents"
        )
        mock_get_grub_default_contents.assert_called_once_with()
        mock_remove.assert_not_called()
        mock_update_grub_default_contents.assert_not_called()

        # Check that the expected output was printed
        mock_print.assert_has_calls(
            [
                call("Reading existing kernel from /boot/grub/grub.cfg..."),
                call("Found submenu entry: test submenu entry"),
                call("Searching for menuentry for kernel 5.4.0-80..."),
                call("Found menuentry: test menuentry"),
                call("Removing 'force partuuid' from grub config..."),
                call("Dry run, not removing the partuuid.cfg file."),
                call("Setting new default: test submenu entry>test menuentry"),
                call("Dry run, not writing to grub config."),
                call("Would have written:"),
                call("GRUB_DEFAULT='test submenu entry>test menuentry'"),
            ]
        )

    @patch("switch_kernel.parse_args")
    @patch("switch_kernel.get_grub_cfg_contents")
    @patch("switch_kernel.get_submenu_entry")
    @patch("switch_kernel.find_menuentry_for_kernel")
    @patch("switch_kernel.get_grub_default_contents")
    @patch("switch_kernel.update_grub_default_contents")
    @patch("builtins.print")
    @patch("os.path.exists")
    @patch("os.remove")
    def test_main_with_efi_run(
        self,
        mock_remove,
        mock_exists,
        mock_print,
        mock_update_grub_default_contents,
        mock_get_grub_default_contents,
        mock_find_menuentry_for_kernel,
        mock_get_submenu_entry,
        mock_get_grub_cfg_contents,
        mock_parse_args,
    ):
        # Set up mocks
        mock_parse_args.return_value = argparse.Namespace(
            kernel=["5.4.0-80"], dry_run=False, enable_efi_vars=True
        )
        mock_get_grub_cfg_contents.return_value = "test grub cfg contents"
        mock_get_submenu_entry.return_value = "test submenu entry"
        mock_find_menuentry_for_kernel.return_value = "test menuentry"
        mock_get_grub_default_contents.return_value = (
            'GRUB_DEFAULT=test grub default contents\nGRUB_CMDLINE_LINUX="quiet splash"'
        )

        # Call main
        main([])

        # Check that the expected functions were called with the expected arguments
        mock_parse_args.assert_called_once_with([])
        mock_get_grub_cfg_contents.assert_called_once_with()
        mock_get_submenu_entry.assert_called_once_with("test grub cfg contents")
        mock_find_menuentry_for_kernel.assert_called_once_with(
            "5.4.0-80", "test grub cfg contents"
        )
        mock_get_grub_default_contents.assert_called_once_with()
        mock_remove.assert_called_once_with("/etc/default/grub.d/40-force-partuuid.cfg")
        # mock_update_grub_default_contents.assert_called_once_with(
        #    "GRUB_DEFAULT='test submenu entry>test menuentry'"
        # )
        mock_update_grub_default_contents.assert_called_once_with(
            "GRUB_DEFAULT='test submenu entry>test menuentry'\n"
            'GRUB_CMDLINE_LINUX="quiet splash efi=runtime"'
        )

        # Check that the expected output was printed
        mock_print.assert_has_calls(
            [
                call("Reading existing kernel from /boot/grub/grub.cfg..."),
                call("Found submenu entry: test submenu entry"),
                call("Searching for menuentry for kernel 5.4.0-80..."),
                call("Found menuentry: test menuentry"),
                call("Removing 'force partuuid' from grub config..."),
                call("Setting new default: test submenu entry>test menuentry"),
            ]
        )

    @patch("switch_kernel.parse_args")
    @patch("switch_kernel.get_grub_cfg_contents")
    @patch("switch_kernel.get_submenu_entry")
    @patch("switch_kernel.find_menuentry_for_kernel")
    @patch("switch_kernel.get_grub_default_contents")
    @patch("switch_kernel.update_grub_default_contents")
    @patch("builtins.print")
    @patch("os.path.exists")
    @patch("os.remove")
    def test_main_implied_efi_vars(
        self,
        mock_remove,
        mock_exists,
        mock_print,
        mock_update_grub_default_contents,
        mock_get_grub_default_contents,
        mock_find_menuentry_for_kernel,
        mock_get_submenu_entry,
        mock_get_grub_cfg_contents,
        mock_parse_args,
    ):
        # Set up mocks
        mock_parse_args.return_value = argparse.Namespace(
            kernel=["realtime"], dry_run=False, enable_efi_vars=False
        )
        mock_get_grub_cfg_contents.return_value = "test grub cfg contents"
        mock_get_submenu_entry.return_value = "test submenu entry"
        mock_find_menuentry_for_kernel.return_value = "test menuentry"
        mock_get_grub_default_contents.return_value = (
            'GRUB_DEFAULT=test grub default contents\nGRUB_CMDLINE_LINUX="quiet splash"'
        )

        # Call main
        main([])

        # Check that the expected functions were called with the expected arguments
        mock_parse_args.assert_called_once_with([])
        mock_get_grub_cfg_contents.assert_called_once_with()
        mock_get_submenu_entry.assert_called_once_with("test grub cfg contents")
        mock_find_menuentry_for_kernel.assert_called_once_with(
            "realtime", "test grub cfg contents"
        )
        mock_get_grub_default_contents.assert_called_once_with()
        mock_remove.assert_called_once_with("/etc/default/grub.d/40-force-partuuid.cfg")
        # mock_update_grub_default_contents.assert_called_once_with(
        #    "GRUB_DEFAULT='test submenu entry>test menuentry'"
        # )
        mock_update_grub_default_contents.assert_called_once_with(
            "GRUB_DEFAULT='test submenu entry>test menuentry'\n"
            'GRUB_CMDLINE_LINUX="quiet splash efi=runtime"'
        )

        # Check that the expected output was printed
        mock_print.assert_has_calls(
            [
                call("Reading existing kernel from /boot/grub/grub.cfg..."),
                call("Found submenu entry: test submenu entry"),
                call("Searching for menuentry for kernel realtime..."),
                call("Found menuentry: test menuentry"),
                call("Removing 'force partuuid' from grub config..."),
                call("Setting new default: test submenu entry>test menuentry"),
            ]
        )
