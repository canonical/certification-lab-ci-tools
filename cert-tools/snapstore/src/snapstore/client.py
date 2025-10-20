"""
A client for interacting with endpoints of the snap Store API.

Ref: https://api.snapcraft.io/docs/
"""

from craft_store import BaseClient, HTTPClient


class SnapstoreClient:
    """
    Interact with endpoints of the snap Store API
    """

    snapstore_url = "https://api.snapcraft.io"

    def __init__(self, base_client: BaseClient | HTTPClient):
        self.base_client = base_client

    def get_authorization_header(self) -> str:
        try:
            return self.base_client._get_authorization_header()
        except AttributeError:
            return None

    def create_headers(
        self, store: str | None = None, headers: dict | None = None
    ) -> dict:
        """
        Return a dict containing the headers for all HTTP requests to the
        snap Store API (combine "standard" headers request-specific ones).
        """
        authorization = self.get_authorization_header()
        return {
            "Snap-Device-Series": "16",
            **(headers if headers else {}),
            **({"Snap-Device-Store": store} if store else {}),
            **({"Authorization": authorization} if authorization else {}),
        }

    def get(
        self,
        endpoint: str,
        params: dict | None = None,
        store: str | None = None,
        headers: dict | None = None,
    ) -> dict:
        """
        Submit a GET request to an endpoint of the snap Store API
        and return a dict with the contents of the response.
        """
        response = self.base_client.request(
            method="GET",
            url=f"{self.snapstore_url}/{endpoint}",
            headers=self.create_headers(store, headers),
            params=(params or {}),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def post(
        self,
        endpoint: str,
        payload: dict,
        store: str | None = None,
        headers: dict | None = None,
    ) -> dict:
        """
        Submit a POST request to an endpoint of the snap Store API
        and return a dict with the contents of the response.
        """
        response = self.base_client.request(
            method="POST",
            url=f"{self.snapstore_url}/{endpoint}",
            headers=self.create_headers(store, headers),
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
