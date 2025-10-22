"""Interface for managing device reboots."""

import logging

from toolbox.interfaces import DeviceInterface


logger = logging.getLogger(__name__)


class RebootInterface(DeviceInterface):
    """Provides reboot capabilities for devices."""

    def is_reboot_required(self) -> bool:
        """Check if a reboot is required by testing for /run/reboot-required."""
        result = self.device.run(["test", "-f", "/run/reboot-required"])
        if result:
            logger.info("Reboot required for %s", self.device.host)
        return bool(result)

    def reboot(self) -> bool:
        """Reboot the device."""
        logger.info("Rebooting %s", self.device.host)
        result = self.device.run(["sudo", "reboot"])
        return bool(result)
