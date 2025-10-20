from typing import Iterable

from snapstore.client import SnapstoreClient
from snapstore.snaps import SnapSpecifier


class SnapstoreInfo:
    """
    Retrieve snap info through the snap Store API

    Ref:
    - https://api.snapcraft.io/docs/refresh.html
    - https://api.snapcraft.io/docs/info.html
    """

    def __init__(self, client: SnapstoreClient):
        self.client = client

    def get_snap_info(
        self,
        snap: str,
        architecture: str | None = None,
        store: str | None = None,
        fields: Iterable[str] | None = None,
    ) -> dict:
        """
        Return info for a specific snap, as retrieved from the
        `v2/snaps/info/{snap}` endpoint of the snap Store API.

        The result contains a `channel-map` with information about
        the different channels on which the snap is published.

        Ref: https://api.snapcraft.io/docs/info.html
        """
        params = {}
        if architecture:
            params["architecture"] = architecture
        if fields:
            params["fields"] = ",".join(field.strip() for field in fields)
        return self.client.get(
            endpoint=f"v2/snaps/info/{snap}",
            params=params,
            store=store,
        )

    def get_refresh_info(
        self,
        snap_specifiers: Iterable[SnapSpecifier],
        architecture: str,
        store: str | None = None,
        fields: Iterable[str] | None = None,
    ) -> dict:
        """
        Return info for a collection of snaps, as retrieved from the
        `v2/snaps/refresh` endpoint of the snap Store API.

        Ref: https://api.snapcraft.io/docs/refresh.html
        """
        payload = {
            "context": [],
            "actions": [
                {
                    "name": snap.name,
                    "channel": str(snap.channel),
                    "action": "download",
                    "instance-key": snap.name,
                }
                for snap in snap_specifiers
            ],
        }
        if fields:
            payload["fields"] = sorted(fields)
        response = self.client.post(
            endpoint="v2/snaps/refresh",
            payload=payload,
            store=store,
            headers={"Snap-Device-Architecture": architecture},
        )
        return response["results"]
