"""Interface for communicating with the snapd REST API over sockets.

Reference: https://snapcraft.io/docs/snapd-api
"""

from contextlib import suppress
from io import StringIO
import json
import re
from urllib.parse import urlencode
import yaml

from toolbox.interfaces import DeviceInterface


class SnapdAPIError(Exception):
    pass


class SnapdAPIClient(DeviceInterface):
    """Client for the snapd REST API.

    At the moment, only GET requests to the API are supported. Essentially,
    this is for retrieving detailed snap information in an easy-to-process
    format, instead of using `snap` commands and parsing their output.

    Here's an example of the equivalent manual way of submitting a GET request
    to a snapd API endpoint and retrieving the response:
    ```
    printf 'GET /v2/connections?select=all HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n' | \
    nc -U /run/snapd.socket
    ```
    Note that `curl` could also be used but is not installed by default on
    all devices.
    """

    @staticmethod
    def create_get_request_url(endpoint: str, params: dict = None) -> str:
        """Build the GET request URL for a snapd API endpoint."""
        query = "?" + urlencode(params, doseq=True) if params else ""
        return f"GET /v2/{endpoint}{query}"

    @staticmethod
    def create_get_request(url: str) -> str:
        """Build the HTTP request string for the given URL."""
        return f"{url} HTTP/1.1\nHost: snapd.socket\nConnection: close\n\n"

    @staticmethod
    def parse_header(raw_header: str) -> dict:
        """Parse HTTP response header into a dictionary."""
        header_lines = [line.strip() for line in re.split(r"\n|\r\n", raw_header)]
        status = header_lines[0].split(maxsplit=2)
        header = {"status": {"status-code": status[1]}}
        with suppress(IndexError):
            header["status"]["reason"] = status[2]
        for header_line in header_lines[1:]:
            with suppress(ValueError):
                field, value = header_line.split(": ")
                header[field] = value
        return header

    def parse_chunked_body(raw_body: str) -> str:
        """Parse HTTP response body that has been chunked transfer-encoded.

        https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Transfer-Encoding#chunked
        """
        body_parts = []
        chunk_size_hex, raw_body = re.split(r"\n|\r\n", raw_body, maxsplit=1)
        chunk_size = int(chunk_size_hex.strip(), base=16)
        while chunk_size > 0:
            body_parts.append(raw_body[:chunk_size])
            raw_body = raw_body[chunk_size:].lstrip()
            chunk_size_hex, raw_body = re.split(r"\n|\r\n", raw_body, maxsplit=1)
            chunk_size = int(chunk_size_hex.strip(), base=16)
        return "".join(body_parts)

    @classmethod
    def parse(cls, response: str) -> tuple[dict, str]:
        """Parse HTTP response into header dict and body string."""
        raw_header, raw_body = re.split(r"\n\n|\r\n\r\n", response, maxsplit=1)
        header = cls.parse_header(raw_header)
        if header.get("Transfer-Encoding") == "chunked":
            body = cls.parse_chunked_body(raw_body)
        else:
            body = raw_body
        return header, body

    @staticmethod
    def parse_json(response: str) -> dict[str, str]:
        """Extract and parse JSON content from response body."""
        json_match = re.search(r"{.*}", response, re.DOTALL)
        if json_match is None:
            raise SnapdAPIError(
                f"Unable to extract application/json content from response: {response}"
            )
        json_contents_str = json_match.group(0)
        try:
            json_contents = json.loads(json_contents_str)
        except json.decoder.JSONDecodeError as error:
            raise SnapdAPIError(
                f"Unable to parse application/json content: {json_contents_str}"
            ) from error
        return json_contents

    @staticmethod
    def parse_assertions(body: str) -> dict:
        """Parse assertion content from response body."""
        parts = re.split(r"\n\n|\r\n\r\n", body)
        try:
            return [yaml.safe_load(part) for part in parts[:-1]]
        except yaml.YAMLError as error:
            raise SnapdAPIError(
                f"Unable to parse application/x.ubuntu.assertion content: {body}"
            ) from error

    def get(self, endpoint: str, params: dict = None) -> dict:
        """Make a GET request to a snapd API endpoint and return the result."""
        url = self.create_get_request_url(endpoint, params)
        request = self.create_get_request(url)
        response = self.device.run(
            ["nc", "-U", "/run/snapd.socket"],
            in_stream=StringIO(request),
            echo_stdin=False,
            hide=True,
        )
        if not response.stdout:
            raise SnapdAPIError(response.stderr if response.stderr else "No response")
        header, body = self.parse(response.stdout)
        status = header["status"]
        if status["status-code"] != "200":
            try:
                reason_message = f" ({status['reason']})"
            except KeyError:
                reason_message = ""
            raise SnapdAPIError(
                f"Response {status['status-code']}{reason_message} to request {url}"
            )
        content_type = header.get("Content-Type")
        if content_type == "application/json":
            return self.parse_json(body)["result"]
        if content_type == "application/x.ubuntu.assertion":
            return self.parse_assertions(body)
        raise SnapdAPIError(f"Unable to parse content type: {content_type}")
