from craft_store import endpoints, HTTPClient, UbuntuOneStoreClient
from craft_store.errors import CraftStoreError


BASE_URL = "https://dashboard.snapcraft.io"
STORAGE_BASE_URL = "https://upload.apps.staging.ubuntu.com"
AUTH_URL = "https://login.ubuntu.com"

USER_AGENT = "Certification client"
APPLICATION = "cert-tools/snapstore"


def create_ubuntu_one_store_client(
    token_environment_variable: str,
) -> UbuntuOneStoreClient:
    """
    Return an authenticated craft-store client for the Snap store

    Raise a (derived) instance of `CraftStoreError` if the token
    stored in `token_environment_variable` cannot be used successfully
    for authenticating to the Snap store.
    """
    client = UbuntuOneStoreClient(
        base_url=BASE_URL,
        storage_base_url=STORAGE_BASE_URL,
        auth_url=AUTH_URL,
        endpoints=endpoints.U1_SNAP_STORE,
        environment_auth=token_environment_variable,
        user_agent=USER_AGENT,
        application_name=APPLICATION,
    )
    # raise exception if authentication has been unsuccessful
    client.whoami()
    return client


def create_http_client() -> HTTPClient:
    """
    Return a simple craft-store HTTP client for the Snap store
    """
    return HTTPClient(user_agent=USER_AGENT)


def create_base_client(
    token_environment_variable: str | None = None,
) -> UbuntuOneStoreClient | HTTPClient:
    """
    Return a craft-store client for the Snap store

    The token stored in `token_environment_variable` (if any) will be used
    to attempt authenticating the client.

    Both types of craft-store client returned have the same requests-like
    interface that can be used to submit requests to the Snap store API.
    """
    try:
        return create_ubuntu_one_store_client(token_environment_variable)
    except CraftStoreError:
        return create_http_client()
