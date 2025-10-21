from dataclasses import replace
import re

from snapstore.client import SnapstoreClient
from snapstore.info import SnapstoreInfo
from toolbox.devices import Device
from toolbox.entities.snaps import SnapSpecifier


class CheckboxRuntimeHelper:
    def __init__(self, device: Device, snapstore: SnapstoreClient):
        self.device = device
        self.info = SnapstoreInfo(snapstore)

    def get_base(self, snap: SnapSpecifier, arch: str, store: str) -> str | None:
        response = self.info.get_refresh_info(
            snap_specifiers=[snap],
            architecture=arch,
            store=store,
            fields=["base"],
        )
        # extract what should be a single result from the response
        if len(response) != 1:
            raise ValueError(f"Multiple results for {snap} on {arch}")
        result = response[0]
        # check for errors
        if result["result"] == "error":
            raise ValueError(f"{snap} on {arch}: {result['error']['message']}")
        return result["snap"].get("base")

    @staticmethod
    def determine_checkbox_runtime_name(base: str | None) -> str:
        if not base or base == "core":
            return "checkbox16"
        else:
            match = re.search(r"^core([0-9]{2})$", base)
            if match:
                return f"checkbox{match.group(1)}"
            raise ValueError(f"Unable to determine base suffix from {base}")

    def determine_checkbox_runtime(
        self, snap: SnapSpecifier, arch: str, store: str
    ) -> SnapSpecifier:
        base = self.get_base(snap, arch, store)
        return SnapSpecifier(
            name=self.determine_checkbox_runtime_name(base),
            channel=replace(snap.channel, track="latest"),
        )
