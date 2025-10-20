from pytest import raises
from craft_store.errors import CraftStoreError

from snapstore.craft import (
    create_ubuntu_one_store_client,
    create_http_client,
    create_base_client,
)


class TestCreateUbuntuOneStoreClient:
    """Test cases for create_ubuntu_one_store_client function"""

    def test_successful_creation(self, mocker):
        """Test successful client creation and authentication"""
        mock_ubuntu_client_class = mocker.patch("snapstore.craft.UbuntuOneStoreClient")
        mock_ubuntu_client = mock_ubuntu_client_class.return_value
        mock_ubuntu_client.whoami.return_value = {}

        result = create_ubuntu_one_store_client("TOKEN")

        # UbuntuOneStoreClient (mock) client has been created
        assert result == mock_ubuntu_client
        # the name of the variable holding the token has been passed on
        assert mock_ubuntu_client_class.call_args[1]["environment_auth"] == "TOKEN"
        # `whoami` has been called to verify successful authentication
        mock_ubuntu_client.whoami.assert_called_once()

    def test_authentication_failure(self, mocker):
        """Test handling of authentication failure"""
        mock_ubuntu_client_class = mocker.patch("snapstore.craft.UbuntuOneStoreClient")
        mock_ubuntu_client = mock_ubuntu_client_class.return_value
        mock_ubuntu_client.whoami.side_effect = CraftStoreError("Authentication failed")

        # problems with the token raise a `CraftStoreError`
        with raises(CraftStoreError, match="Authentication failed"):
            create_ubuntu_one_store_client("INVALID_TOKEN")


class TestCreateHttpClient:
    """Test cases for create_http_client function"""

    def test_successful_creation(self, mocker):
        """Test successful client creation"""

        mock_http_client_class = mocker.patch("snapstore.craft.HTTPClient")
        mock_http_client = mock_http_client_class.return_value

        result = create_http_client()

        # HTTPClient (mock) client has been created
        assert result == mock_http_client


class TestCreateBaseClient:
    """Test cases for create_base_client function"""

    def test_authenticated(self, mocker):
        """Test creation with valid token"""
        mock_ubuntu_client_class = mocker.patch("snapstore.craft.UbuntuOneStoreClient")
        mock_ubuntu_client = mock_ubuntu_client_class.return_value
        mock_http_client_class = mocker.patch("snapstore.craft.HTTPClient")

        result = create_base_client("TOKEN")

        assert result == mock_ubuntu_client
        mock_ubuntu_client_class.assert_called_once()
        mock_http_client_class.assert_not_called()

    def test_not_authenticated(self, mocker):
        """Test creation with invalid token"""
        mock_ubuntu_client_class = mocker.patch("snapstore.craft.UbuntuOneStoreClient")
        mock_ubuntu_client = mock_ubuntu_client_class.return_value
        mock_ubuntu_client.whoami.side_effect = CraftStoreError("Authentication failed")
        mock_http_client_class = mocker.patch("snapstore.craft.HTTPClient")
        mock_http_client = mock_http_client_class.return_value

        result = create_base_client("TOKEN")

        assert result == mock_http_client
        mock_ubuntu_client_class.assert_called_once()
        mock_http_client_class.assert_called_once()

    def test_propagates_non_craft_store_errors(self, mocker):
        """Test that non-CraftStoreError exceptions are propagated"""
        mock_ubuntu_client_class = mocker.patch("snapstore.craft.UbuntuOneStoreClient")
        mock_ubuntu_client_class.side_effect = Exception("Unexpected error")

        with raises(Exception, match="Unexpected error"):
            create_base_client("TOKEN")
