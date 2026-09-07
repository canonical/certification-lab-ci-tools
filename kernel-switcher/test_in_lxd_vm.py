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
This is a test script for the kernel switcher.
It uses LXD to create a VM in which the test script runs this sequence:
- install a kernel that's older than the default
- reboot
- check that the old kernel is _still not_ running
- use the kernel switch tool to switch to the old kernel
- reboot
- check that the older kernel is running
"""

import shlex
import signal
import subprocess
import time


class VMContext:
    def __init__(self, vm_name):
        self.interrupted = False
        self.first_interrupt_time = None
        signal.signal(signal.SIGINT, self.signal_handler)
        self.vm_name = vm_name

    def __enter__(self):
        print(f"Creating '{self.vm_name}' VM...")

        self._run_host_command(
            f"lxc launch ubuntu:22.04 {self.vm_name} --vm -c security.secureboot=false"
        )
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if not self.interrupted:
            # if the interrupt already happened, the command to delete the vm
            # was already issued
            self._delete_vm()

    def signal_handler(self, signum, frame):
        if not self.interrupted:
            # let's start measuring time now
            self.first_interrupt_time = time.time()
        if self.interrupted and time.time() > self.first_interrupt_time + 2:
            print("\nForced exit.You'll have to do the cleanup yourself.")
            raise KeyboardInterrupt

        self.interrupted = True
        print(
            "\nCTRL+C detected while using a VM...\n"
            "Press CTRL+C again in 2 seconds if you really want to force exit"
        )
        self._delete_vm()
        raise SystemExit("Stopped by the user")

    def _delete_vm(self):
        print(f"Deleting '{self.vm_name}' VM...")
        self._run_host_command(f"lxc delete --force {self.vm_name}")

    def _run_host_command(self, cmd, supress=False):
        """Executes a command on the host and returns the output."""
        try:
            cmd_list = shlex.split(cmd)
            result = subprocess.run(
                cmd_list,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as exc:
            if not supress:
                print(f"Error while running command: {cmd}")
                print(f"Error message: {exc.output}")
            raise

    def run_vm_command(self, cmd, supress=False):
        """Executes a command inside the VM and returns the output."""
        print(f"Running command inside VM: {cmd}")
        full_cmd = f"lxc exec {self.vm_name} -- {cmd}"
        return self._run_host_command(full_cmd, supress)

    def wait_for_vm_ready(self, timeout=60):
        """Waits until the VM is responsive."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                self.run_vm_command("true", supress=True)
                return
            except subprocess.CalledProcessError:
                time.sleep(1)
        raise TimeoutError(
            f"VM '{self.vm_name}' did not become ready within {timeout} seconds."
        )


def extract_kernel_pkgs_from_apt_log(apt_log):
    """
    Returns the name of the kernel package from the apt log.

    >>> text = '''
    ... linux-image-5.4.0-80-generic/focal-updates,rubbish [more rubbish]]]
    ... linux-image-5.4.0-81-generic/focal-updates, no rubbish
    ... at all!
    ... well almost, okay, one more linux-image like incoming
    ... linux-image-5.15.0-1041-kvm/jammy-updates 5.15.0-1041.46 amd64'''
    >>> extract_kernel_pkgs_from_apt_log(text) == [
    ...     'linux-image-5.4.0-80-generic',
    ...     'linux-image-5.4.0-81-generic',
    ...     'linux-image-5.15.0-1041-kvm']
    True
    """
    # list comprehension here would be unreadable due to line length
    # let's do this imperatively
    # not using a regex because even here it may be easier to understand
    # with just python's string methods
    extraceted_pkgs = []

    for line in apt_log.splitlines():
        if line.startswith("linux-image"):
            extraceted_pkgs.append(line.split("/")[0])
    return extraceted_pkgs


def main():
    with VMContext("vm-test") as vm:
        # Wait for VM to be ready
        time.sleep(10)
        vm.wait_for_vm_ready()
        original_kernel = vm.run_vm_command("uname -r")
        print(f"Original kernel: {original_kernel}")
        vm.run_vm_command("apt update")
        pkgs = extract_kernel_pkgs_from_apt_log(
            vm.run_vm_command("apt search 'linux-image.*-kvm'")
        )
        # the first entry in pkgs should be the oldest version of a kvm kernel
        # let's install it
        print(f"Installing 'oldest' available kernel {pkgs[0]}...")
        vm.run_vm_command(f"apt install -y {pkgs[0]}")
        print("copying the kernel switcher to the VM...")
        subprocess.run(["lxc", "file", "push", "switch_kernel.py", "vm-test/root/"])
        print("Running the kernel switcher...")
        new_kernel = pkgs[0].replace("linux-image-", "")
        vm.run_vm_command(f"python3 switch_kernel.py --enable-efi-vars {new_kernel}")
        print("Rebooting VM...")
        vm.run_vm_command("reboot")
        # we have to wait a few seconds to let the VM reboot
        time.sleep(10)
        print("Waiting for VM to come back...")
        vm.wait_for_vm_ready()
        new_kernel = vm.run_vm_command("uname -r")
        print(f"New kernel: {new_kernel}")
        kernel_cmdline = vm.run_vm_command("cat /proc/cmdline")
        if "efi=runtime" not in kernel_cmdline:
            raise SystemExit("'efi=runtime' not found in kernel cmdline")


if __name__ == "__main__":
    main()
