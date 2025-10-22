import logging

from toolbox.interfaces import DeviceInterface


logger = logging.getLogger(__name__)


class RebootInterface(DeviceInterface):
    def is_reboot_required(self) -> bool:
        result = self.device.run(["test", "-f", "/run/reboot-required"])
        if result:
            logger.info("Reboot required for %s", self.device.host)
        return bool(result)

    def reboot(self) -> bool:
        logger.info("Rebooting %s", self.device.host)
        result = self.device.run(["sudo", "reboot"])
        return bool(result)
