from toolbox.interfaces import DeviceInterface


class ArchInterface(DeviceInterface):
    ubuntu_architecture_map = {
        "x86_64": "amd64",
        "aarch64": "arm64",
        "armv7l": "armhf",
        "i686": "i386",
    }

    def get_ubuntu_arch(self) -> str:
        result = self.device.run(["uname", "-m"], hide=True)
        uname_arch = result.stdout.strip()
        return self.ubuntu_architecture_map.get(uname_arch, uname_arch)
