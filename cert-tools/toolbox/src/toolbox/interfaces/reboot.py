from toolbox.interfaces import DeviceInterface


class RebootInterface(DeviceInterface):
    def reboot_required(self) -> bool:
        result = self.device.run(["test", "-f", "/run/reboot-required"])
        return result.exited == 0

    def reboot(self) -> bool:
        result = self.device.run(["sudo", "reboot"])
        return result.exited == 0
