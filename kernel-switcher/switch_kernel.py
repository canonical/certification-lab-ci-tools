#!/usr/bin/env python3
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

"""
This program selects the kernel to boot into.
"""

import argparse
import os
import re
import subprocess
import sys


def get_submenu_entry(grub_cfg_contents: str):
    """
    Returns the identifier of the "advanced" submenu entry from the contents
    of /boot/grub/grub.cfg.

    :param grub_cfg_contents: the contents of /boot/grub/grub.cfg
    :return: the identifier of the "advanced" submenu entry
    :raises SystemExit: if the identifier could not be found
    """

    for line in grub_cfg_contents.splitlines():
        if "submenu" in line and "Advanced" in line:
            identifier = line.split()[6]
            return identifier.replace("'", "")
    raise SystemExit("Could not find submenu entry in grub.cfg")


def assert_root():
    """
    Do nothing if the user is root, otherwise exit the program wit han error.
    """
    if os.geteuid() != 0:
        raise SystemExit("This program must be run as root.")


def find_menuentry_for_kernel(keyword: str, grub_cfg_contents: str):
    """
    Returns the menuentry for the kernel that matches the keyword.

    :param keyword: the keyword to search for
    :param grub_cfg_contents: the contents of /boot/grub/grub.cfg
    :return: the menuentry for the kernel that matches the keyword
    :raises SystemExit: if the adequate menuentry could not be found
    """

    for line in grub_cfg_contents.splitlines():
        if "menuentry" in line and keyword in line and "recovery" not in line:
            # Searching for the pattern using a regular expression
            match = re.search(r"\w*gnulinux.*\w", line)
            if match:
                return match.group()
    raise SystemExit("Could not find kernel in grub.cfg")


def get_grub_cfg_contents():
    """
    Returns the contents of /boot/grub/grub.cfg.

    :return: the contents of /boot/grub/grub.cfg
    :raises SystemExit: if the file could not be read
    """

    try:
        with open("/boot/grub/grub.cfg", "rt") as grub_cfg:
            return grub_cfg.read()
    except OSError as e:
        raise SystemExit(f"Could not read /boot/grub/grub.cfg: {e}")


def get_grub_default_contents():
    """
    Returns the contents of /etc/default/grub.

    :return: the contents of /etc/default/grub
    :raises SystemExit: if the file could not be read
    """

    try:
        with open("/etc/default/grub", "rt") as grub_default:
            return grub_default.read()
    except OSError as e:
        raise SystemExit(f"Could not read /etc/default/grub: {e}")


def update_grub_default_contents(new_grub_default_contents):
    """
    Writes the contents of /etc/default/grub and applies the changes.

    :return: the contents of /etc/default/grub
    :raises SystemExit: if the file could not be read
    """

    try:
        with open("/etc/default/grub", "wt") as grub_default:
            grub_default.write(new_grub_default_contents)
    except OSError as e:
        raise SystemExit(f"Could not write /etc/default/grub: {e}")
    print("Updating grub...")
    subprocess.run(["update-grub"])
    print("Done.")


def parse_args(argv):
    """
    Parse the command line arguments.

    :param argv: the command line arguments
    :return: a pair with the important arguments
    """

    parser = argparse.ArgumentParser(description="Select the kernel to boot into.")
    parser.add_argument(
        "kernel",
        metavar="KERNEL",
        type=str,
        nargs=1,
        help="the kernel to boot into",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="do not write anything to the grub config",
    )

    parser.add_argument(
        "--enable-efi-vars",
        action="store_true",
        help="enable EFI variables so MAAS can reprovision the machine",
    )

    return parser.parse_args(argv[1:])


def add_efi_opt(cmdline):
    """
    Add the EFI variables to the kernel command line.

    If an efi setting is already there replace it with the `runtime` option.
    """
    if not cmdline:
        return "efi=runtime"
    if "efi=" in cmdline:
        return re.sub(r"efi=\S*", "efi=runtime", cmdline)

    return cmdline + " efi=runtime"


def update_cmd_linux(grub_cfg_contents):
    """
    Goes through the context of the grub config file,
    finds the line with the `GRUB_CMDLINE_LINUX` and
    adds the `efi` option to it.
    """
    output = []

    for line in grub_cfg_contents.splitlines():
        pattern = r'GRUB_CMDLINE_LINUX="(.*?)"'
        match = re.search(pattern, line)
        if match:
            value = match.group(1)
            output.append(f'GRUB_CMDLINE_LINUX="{add_efi_opt(value)}"')

        else:
            output.append(line)
    return "\n".join(output)


def main(argv):
    args = parse_args(argv)
    kernel = args.kernel[0]
    dry_run = args.dry_run
    enable_efi_vars = args.enable_efi_vars

    print("Reading existing kernel from /boot/grub/grub.cfg...")
    grub_cfg_contents = get_grub_cfg_contents()
    submenu_entry = get_submenu_entry(grub_cfg_contents)
    print(f"Found submenu entry: {submenu_entry}")

    print(f"Searching for menuentry for kernel {kernel}...")
    menuentry = find_menuentry_for_kernel(kernel, grub_cfg_contents)
    print(f"Found menuentry: {menuentry}")

    # let's remove the "force partuuid" file from the grub config
    # otherwise the kernel will not boot
    print("Removing 'force partuuid' from grub config...")
    file_path = "/etc/default/grub.d/40-force-partuuid.cfg"
    if dry_run:
        print("Dry run, not removing the partuuid.cfg file.")
    elif os.path.exists(file_path):
        os.remove(file_path)
    else:
        print("partuuid.cfg not found, not removing.")

    new_default = f"{submenu_entry}>{menuentry}"
    print(f"Setting new default: {new_default}")

    grub_default_contents = get_grub_default_contents()
    new_grub_default_contents = re.sub(
        r"GRUB_DEFAULT=.*",
        f"GRUB_DEFAULT='{new_default}'",
        grub_default_contents,
    )
    if enable_efi_vars or kernel.lower() == "realtime":
        new_grub_default_contents = update_cmd_linux(new_grub_default_contents)

    if dry_run:
        print("Dry run, not writing to grub config.")
        print("Would have written:")
        print(new_grub_default_contents)
        return
    update_grub_default_contents(new_grub_default_contents)


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv)
