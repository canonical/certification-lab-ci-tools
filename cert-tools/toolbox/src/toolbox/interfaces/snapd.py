from io import StringIO
import json
import re
from urllib.parse import urlencode
import yaml

from toolbox.interfaces import DeviceInterface


class SnapdAPIError(Exception):
    pass


class SnapdAPIClient(DeviceInterface):
    @staticmethod
    def create_get_request_url(endpoint: str, params: dict = None) -> str:
        query = "?" + urlencode(params, doseq=True) if params else ""
        return f"GET /v2/{endpoint}{query}"

    @staticmethod
    def create_get_request(url: str) -> str:
        return f"{url} HTTP/1.1\nHost: placeholder\nConnection: close\n\n"

    @staticmethod
    def parse_status(response: str) -> dict[str, str]:
        status_match = re.search(
            r"^HTTP/\d+\.\d+\s+(?P<status_code>\d{3})(?:\s+(?P<reason>.*?))?\s*$",
            response,
            re.MULTILINE,
        )
        if not status_match:
            raise SnapdAPIError(f"Unable to extract status from response: {response}")
        return status_match.groupdict()

    @staticmethod
    def parse_content_type(response: str) -> dict[str, str]:
        content_match = re.search(
            r"^Content-Type: (?P<content_type>.*?)\s*$", response, re.MULTILINE
        )
        return content_match.group("content_type")

    @staticmethod
    def parse_json(response: str) -> dict[str, str]:
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
    def parse_assertions(response: str) -> dict:
        parts = re.split(r"\n\n|\r\n\r\n", response)
        return [yaml.safe_load(part) for part in parts[1:-1]]

    def get(self, endpoint: str, params: dict = None) -> dict:
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
        status = self.parse_status(response.stdout)
        if status["status_code"] != "200":
            try:
                reason_message = f" ({status['reason']})"
            except KeyError:
                reason_message = ""
            raise SnapdAPIError(
                f"Response {status['status_code']}{reason_message} to request {url}"
            )
        content_type = self.parse_content_type(response.stdout)
        if content_type == "application/json":
            return self.parse_json(response.stdout)["result"]
        if content_type == "application/x.ubuntu.assertion":
            return self.parse_assertions(response.stdout)
        raise SnapdAPIError(f"Unable to parse content type: {content_type}")
