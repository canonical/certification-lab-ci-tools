from dataclasses import replace
import re

from snapstore.client import SnapstoreClient
from snapstore.info import Info
from toolbox.devices import Device
from toolbox.entities.snaps import SnapSpecifier
from toolbox.interfaces.snapd import SnapdAPIClient


class CheckboxRuntimeHelper:
    def __init__(self, device: Device, snapstore: SnapstoreClient):
        self.device = device
        self.info = Info(snapstore)

    @staticmethod
    def determine_checkbox_runtime_name(base: str | None) -> str:
        if not base or base == "core":
            return "checkbox16"
        else:
            match = re.search(r"^core([0-9]{2})$", base)
            if match:
                return f"checkbox{match.group(1)}"
            raise ValueError(f"Unable to determine base suffix from {base}")

    def determine_checkbox_runtime(self, snap: SnapSpecifier) -> SnapSpecifier:
        system_info = self.device.interfaces[SnapdAPIClient].get("system-info")
        store = system_info.get("store")
        response = self.info.info_from_refresh(
            snap=snap.name,
            channel=str(snap.channel),
            architecture=system_info["architecture"],
            store=store,
            fields=["base"],
        )
        base = response.get("base")
        return SnapSpecifier(
            name=self.determine_checkbox_runtime_name(base),
            channel=replace(snap.channel, track="latest"),
        )
