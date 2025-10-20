from pytest import raises, fixture
from snapstore.client import SnapstoreClient
from snapstore.craft import HTTPClient, UbuntuOneStoreClient
from requests import HTTPError


class TestSnapstoreClient:
    """Test cases for SnapstoreClient"""

    @fixture
    def http_base_client(self, mocker):
        """Create a mock HTTPClient"""
        return mocker.create_autospec(HTTPClient, instance=True)

    @fixture
    def ubuntu_base_client(self, mocker):
        """Create a mock UbuntuOneStoreClient and patch where it's used"""
        client = mocker.create_autospec(UbuntuOneStoreClient, instance=True)
        client._get_authorization_header.return_value = "Bearer test-token"
        return client

    @fixture
    def snapstore_client(self, http_base_client):
        """Create SnapstoreClient with HTTPClient as base client"""
        return SnapstoreClient(base_client=http_base_client)

    @fixture
    def authorized_snapstore_client(self, ubuntu_base_client):
        """Create SnapstoreClient with UbuntuOneStoreClient as base client"""
        return SnapstoreClient(base_client=ubuntu_base_client)

    def test_no_authorization_header(self, snapstore_client):
        """Test getting authorization header from a non-authorized client"""
        result = snapstore_client.get_authorization_header()
        assert result is None

    def test_authorization_header(self, authorized_snapstore_client):
        """Test getting authorization header from an authorized client"""
        result = authorized_snapstore_client.get_authorization_header()
        assert result == "Bearer test-token"

    def test_create_headers_minimal(self, snapstore_client):
        """Test creating headers with minimal parameters"""
        headers = snapstore_client.create_headers()
        assert headers == {"Snap-Device-Series": "16"}

    def test_create_headers_with_store(self, snapstore_client):
        """Test creating headers with store parameter"""
        headers = snapstore_client.create_headers(store="test-store")
        assert headers == {
            "Snap-Device-Series": "16",
            "Snap-Device-Store": "test-store",
        }

    def test_create_headers_custom(self, snapstore_client):
        """Test creating headers with all parameters"""
        custom = {"X-Custom": "value", "X-Other": "data"}
        headers = snapstore_client.create_headers(headers=custom)
        assert headers == {
            "Snap-Device-Series": "16",
            "X-Custom": "value",
            "X-Other": "data",
        }

    def test_create_headers_full(self, authorized_snapstore_client):
        """Test creating headers with all parameters"""
        custom = {"X-Custom": "value", "X-Other": "data"}
        headers = authorized_snapstore_client.create_headers(
            store="test-store", headers=custom
        )
        assert headers == {
            "Snap-Device-Series": "16",
            "Snap-Device-Store": "test-store",
            "Authorization": "Bearer test-token",
            "X-Custom": "value",
            "X-Other": "data",
        }

    def test_get_success(self, mocker, authorized_snapstore_client):
        """Test successful GET request"""
        expected_result = {"result": "success"}
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = expected_result
        mock_response.raise_for_status.return_value = None
        authorized_snapstore_client.base_client.request.return_value = mock_response

        params = {"key": "value"}
        result = authorized_snapstore_client.get("v2/snaps/test", params=params)

        assert result == expected_result
        _, kwargs = authorized_snapstore_client.base_client.request.call_args
        assert kwargs["method"] == "GET"
        assert kwargs["url"] == f"{SnapstoreClient.snapstore_url}/v2/snaps/test"
        assert kwargs["params"] == params
        mock_response.json.assert_called_once()
        mock_response.raise_for_status.assert_called_once()

    def test_post_success(self, mocker, authorized_snapstore_client):
        """Test successful POST request"""
        expected_result = {"result": "success"}
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = expected_result
        mock_response.raise_for_status.return_value = None
        authorized_snapstore_client.base_client.request.return_value = mock_response

        payload = {"key": "value"}
        result = authorized_snapstore_client.post("v2/snaps/test", payload=payload)

        assert result == expected_result
        _, kwargs = authorized_snapstore_client.base_client.request.call_args
        assert kwargs["method"] == "POST"
        assert kwargs["url"] == f"{SnapstoreClient.snapstore_url}/v2/snaps/test"
        assert kwargs["json"] == payload
        mock_response.json.assert_called_once()
        mock_response.raise_for_status.assert_called_once()

    def test_get_error(self, mocker, authorized_snapstore_client):
        """Test GET request with HTTP error"""
        mock_response = mocker.Mock()
        mock_response.raise_for_status.side_effect = HTTPError()
        authorized_snapstore_client.base_client.request.return_value = mock_response

        with raises(HTTPError):
            authorized_snapstore_client.get("v2/snaps/test")
        mock_response.raise_for_status.assert_called_once()

    def test_post_error(self, mocker, authorized_snapstore_client):
        """Test POST request with HTTP error"""
        mock_response = mocker.Mock()
        mock_response.raise_for_status.side_effect = HTTPError()
        authorized_snapstore_client.base_client.request.return_value = mock_response

        with raises(HTTPError):
            authorized_snapstore_client.post("v2/snaps/test", payload={})
        mock_response.raise_for_status.assert_called_once()
