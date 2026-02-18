"""Tests for the toolbox.interfaces.snapd module."""

import pytest

from invoke import Result
from toolbox.interfaces.snapd import SnapdAPIClient, SnapdAPIError

from tests.devices.trivial import TrivialDevice


class TestRequests:
    """Tests for the SnapdAPIClient requests."""

    @pytest.mark.parametrize(
        "endpoint,params,expected_url",
        [
            # Simple endpoints without parameters
            ("snaps", None, "GET /v2/snaps"),
            ("connections", None, "GET /v2/connections"),
            ("system-info", None, "GET /v2/system-info"),
            # Endpoints with single parameter
            ("snaps", {"name": "checkbox"}, "GET /v2/snaps?name=checkbox"),
            ("connections", {"select": "all"}, "GET /v2/connections?select=all"),
            # Endpoints with multiple parameters
            (
                "snaps",
                {"name": "checkbox", "refresh": "true"},
                "GET /v2/snaps?name=checkbox&refresh=true",
            ),
            # Parameters with special characters (URL encoding)
            (
                "snaps",
                {"name": "my snap"},
                "GET /v2/snaps?name=my+snap",
            ),
            # Empty params dict should be treated like None
            ("snaps", {}, "GET /v2/snaps"),
        ],
    )
    def test_create_get_request_url(self, endpoint, params, expected_url):
        """Test creating GET request URLs for various endpoints and parameters."""
        url = SnapdAPIClient.create_get_request_url(endpoint, params)
        assert url == expected_url

    @pytest.mark.parametrize(
        "url,expected_request",
        [
            (
                "GET /v2/snaps",
                "GET /v2/snaps HTTP/1.1\r\nHost: snapd.socket\r\nConnection: close\r\n\r\n",
            ),
            (
                "GET /v2/connections?select=all",
                "GET /v2/connections?select=all HTTP/1.1\r\nHost: snapd.socket\r\nConnection: close\r\n\r\n",
            ),
        ],
    )
    def test_create_get_request(self, url, expected_request):
        """Test creating HTTP request strings from URLs."""
        request = SnapdAPIClient.create_get_request(url)
        assert request == expected_request


class TestResponses:
    """Tests for SnapdAPIClient parsing methods."""

    @pytest.mark.parametrize(
        "raw_header,expected_header",
        [
            # Basic successful response
            (
                "HTTP/1.1 200 OK\nContent-Type: application/json\nContent-Length: 1234",
                {
                    "status": {"status-code": "200", "reason": "OK"},
                    "Content-Type": "application/json",
                    "Content-Length": "1234",
                },
            ),
            # Response with chunked encoding
            (
                "HTTP/1.1 200 OK\nTransfer-Encoding: chunked\nContent-Type: application/json",
                {
                    "status": {"status-code": "200", "reason": "OK"},
                    "Transfer-Encoding": "chunked",
                    "Content-Type": "application/json",
                },
            ),
            # Error response
            (
                "HTTP/1.1 404 Not Found\nContent-Type: application/json",
                {
                    "status": {"status-code": "404", "reason": "Not Found"},
                    "Content-Type": "application/json",
                },
            ),
            # Response without reason phrase
            (
                "HTTP/1.1 200 \nContent-Type: application/json",
                {
                    "status": {"status-code": "200"},
                    "Content-Type": "application/json",
                },
            ),
            # Response with CRLF line endings
            (
                "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 1234",
                {
                    "status": {"status-code": "200", "reason": "OK"},
                    "Content-Type": "application/json",
                    "Content-Length": "1234",
                },
            ),
        ],
    )
    def test_parse_header(self, raw_header, expected_header):
        """Test parsing HTTP response headers."""
        header = SnapdAPIClient.parse_header(raw_header)
        assert header == expected_header

    @pytest.mark.parametrize(
        "raw_body,expected_body",
        [
            # Single chunk
            (
                "5\nhello\n0\n",
                "hello",
            ),
            # Multiple chunks
            (
                "5\nhello\n6\n world\n0\n",
                "hello world",
            ),
            # Chunks with CRLF
            (
                "5\r\nhello\r\n6\r\n world\r\n0\r\n",
                "hello world",
            ),
            # Hex chunk sizes
            (
                "a\nhello worl\n1\nd\n0\n",
                "hello world",
            ),
        ],
    )
    def test_parse_chunked_body(self, raw_body, expected_body):
        """Test parsing chunked transfer-encoded bodies."""
        body = SnapdAPIClient.parse_chunked_body(raw_body)
        assert body == expected_body

    def test_parse_non_chunked_response(self):
        """Test parsing a non-chunked HTTP response."""
        response = 'HTTP/1.1 200 OK\nContent-Type: application/json\nContent-Length: 13\n\n{"key":"val"}'

        header, body = SnapdAPIClient.parse(response)

        assert header["status"]["status-code"] == "200"
        assert header["Content-Type"] == "application/json"
        assert body == '{"key":"val"}'

    def test_parse_chunked_response(self):
        """Test parsing a chunked HTTP response."""
        response = "HTTP/1.1 200 OK\nTransfer-Encoding: chunked\n\n5\nhello\n0\n"

        header, body = SnapdAPIClient.parse(response)

        assert header["status"]["status-code"] == "200"
        assert header["Transfer-Encoding"] == "chunked"
        assert body == "hello"

    def test_parse_with_crlf(self):
        """Test parsing response with CRLF line endings."""
        response = (
            'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{"key":"val"}'
        )

        header, body = SnapdAPIClient.parse(response)

        assert header["status"]["status-code"] == "200"
        assert body == '{"key":"val"}'

    @pytest.mark.parametrize(
        "response,expected_result",
        [
            # Simple JSON object
            (
                '{"result": {"key": "value"}}',
                {"result": {"key": "value"}},
            ),
            # JSON with whitespace
            (
                '  {"result": {"key": "value"}}  ',
                {"result": {"key": "value"}},
            ),
            # JSON with nested structures
            (
                '{"result": {"snap": "checkbox", "version": "2.0", "channels": ["stable", "edge"]}}',
                {
                    "result": {
                        "snap": "checkbox",
                        "version": "2.0",
                        "channels": ["stable", "edge"],
                    }
                },
            ),
            # JSON with text before it
            (
                'Some text before\n{"result": {"key": "value"}}',
                {"result": {"key": "value"}},
            ),
        ],
    )
    def test_parse_json(self, response, expected_result):
        """Test parsing JSON content from responses."""
        result = SnapdAPIClient.parse_json(response)
        assert result == expected_result

    @pytest.mark.parametrize(
        "invalid_response",
        [
            "No JSON here",
            "[]",  # Array, not object
            "{invalid json}",
            "",
        ],
    )
    def test_parse_json_errors(self, invalid_response):
        """Test that parse_json raises SnapdAPIError for invalid JSON."""
        with pytest.raises(SnapdAPIError):
            SnapdAPIClient.parse_json(invalid_response)

    def test_parse_single_assertion(self):
        """Test parsing a single assertion."""
        body = "type: account\naccount-id: abc123\nusername: testuser\n\n"

        result = SnapdAPIClient.parse_assertions(body)

        assert len(result) == 1
        assert result[0]["type"] == "account"
        assert result[0]["account-id"] == "abc123"
        assert result[0]["username"] == "testuser"

    def test_parse_multiple_assertions(self):
        """Test parsing multiple assertions."""
        body = "type: account\naccount-id: abc123\n\ntype: snap-declaration\nsnap-name: test\n\n"

        result = SnapdAPIClient.parse_assertions(body)

        assert len(result) == 2
        assert result[0]["type"] == "account"
        assert result[1]["type"] == "snap-declaration"

    def test_parse_assertions_with_crlf(self):
        """Test parsing assertions with CRLF line endings."""
        body = "type: account\r\naccount-id: abc123\r\n\r\n"

        result = SnapdAPIClient.parse_assertions(body)

        assert len(result) == 1
        assert result[0]["type"] == "account"

    def test_parse_assertions_error(self):
        """Test that parse_assertions raises SnapdAPIError for invalid YAML."""
        body = "type: account\n  invalid: yaml: structure\n\n"

        with pytest.raises(SnapdAPIError):
            SnapdAPIClient.parse_assertions(body)


class TestGet:
    """Tests for SnapdAPIClient.get() method."""

    def test_get_json_response(self, mocker):
        """Test get() with a JSON response."""
        device = TrivialDevice(interfaces=[SnapdAPIClient()])
        response_text = 'HTTP/1.1 200 OK\nContent-Type: application/json\n\n{"result": {"snap": "checkbox"}}'
        device.run = mocker.Mock(return_value=Result(stdout=response_text, exited=0))

        result = device.interfaces[SnapdAPIClient].get("snaps")

        assert result == {"snap": "checkbox"}
        device.run.assert_called_once()
        call_args = device.run.call_args
        assert call_args[0][0] == ["nc", "-q", "1", "-U", "/run/snapd.socket"]

    def test_get_with_parameters(self, mocker):
        """Test get() with query parameters."""
        device = TrivialDevice(interfaces=[SnapdAPIClient()])
        response_text = (
            'HTTP/1.1 200 OK\nContent-Type: application/json\n\n{"result": []}'
        )
        device.run = mocker.Mock(return_value=Result(stdout=response_text, exited=0))

        result = device.interfaces[SnapdAPIClient].get("connections", {"select": "all"})

        assert result == []
        device.run.assert_called_once()

    def test_get_assertions_response(self, mocker):
        """Test get() with an assertions response."""
        device = TrivialDevice(interfaces=[SnapdAPIClient()])
        response_text = "HTTP/1.1 200 OK\nContent-Type: application/x.ubuntu.assertion\n\ntype: account\naccount-id: abc123\n\n"
        device.run = mocker.Mock(return_value=Result(stdout=response_text, exited=0))

        result = device.interfaces[SnapdAPIClient].get("assertions/account/abc123")

        assert len(result) == 1
        assert result[0]["type"] == "account"

    def test_get_no_response(self, mocker):
        """Test get() when there's no response."""
        device = TrivialDevice(interfaces=[SnapdAPIClient()])
        device.run = mocker.Mock(
            return_value=Result(stdout="", stderr="Connection failed", exited=1)
        )

        with pytest.raises(SnapdAPIError, match="Connection failed"):
            device.interfaces[SnapdAPIClient].get("snaps")

    def test_get_no_response_no_stderr(self, mocker):
        """Test get() when there's no response and no stderr."""
        device = TrivialDevice(interfaces=[SnapdAPIClient()])
        device.run = mocker.Mock(return_value=Result(stdout="", stderr="", exited=1))

        with pytest.raises(SnapdAPIError, match="No response"):
            device.interfaces[SnapdAPIClient].get("snaps")

    def test_get_non_200_response(self, mocker):
        """Test get() with a non-200 status code."""
        device = TrivialDevice(interfaces=[SnapdAPIClient()])
        response_text = 'HTTP/1.1 404 Not Found\nContent-Type: application/json\n\n{"error": "not found"}'
        device.run = mocker.Mock(return_value=Result(stdout=response_text, exited=0))

        with pytest.raises(SnapdAPIError, match="Response.*404.*Not Found"):
            device.interfaces[SnapdAPIClient].get("snaps/nonexistent")

    def test_get_non_200_response_no_reason(self, mocker):
        """Test get() with a non-200 status code without reason phrase."""
        device = TrivialDevice(interfaces=[SnapdAPIClient()])
        response_text = 'HTTP/1.1 500 \nContent-Type: application/json\n\n{"error": "internal error"}'
        device.run = mocker.Mock(return_value=Result(stdout=response_text, exited=0))

        with pytest.raises(SnapdAPIError):
            device.interfaces[SnapdAPIClient].get("snaps")

    def test_get_unsupported_content_type(self, mocker):
        """Test get() with an unsupported content type."""
        device = TrivialDevice(interfaces=[SnapdAPIClient()])
        response_text = (
            "HTTP/1.1 200 OK\nContent-Type: text/plain\n\nPlain text response"
        )
        device.run = mocker.Mock(return_value=Result(stdout=response_text, exited=0))

        with pytest.raises(SnapdAPIError, match="Unable to parse content type"):
            device.interfaces[SnapdAPIClient].get("snaps")

    def test_get_chunked_response(self, mocker):
        """Test get() with a chunked transfer-encoded response."""
        device = TrivialDevice(interfaces=[SnapdAPIClient()])
        response_text = 'HTTP/1.1 200 OK\nTransfer-Encoding: chunked\nContent-Type: application/json\n\n20\n{"result": {"snap": "checkbox"}}\n0\n'
        device.run = mocker.Mock(return_value=Result(stdout=response_text, exited=0))

        result = device.interfaces[SnapdAPIClient].get("snaps")

        assert result == {"snap": "checkbox"}
