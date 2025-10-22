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
    @staticmethod
    def create_get_request_url(endpoint: str, params: dict = None) -> str:
        query = "?" + urlencode(params, doseq=True) if params else ""
        return f"GET /v2/{endpoint}{query}"

    @staticmethod
    def create_get_request(url: str) -> str:
        return f"{url} HTTP/1.1\nHost: placeholder\nConnection: close\n\n"

    @staticmethod
    def parse_header(raw_header: str) -> dict:
        header_lines = [line.strip() for line in raw_header.split("\n")]
        status = header_lines[0].split(maxsplit=2)
        header = {
            "status": {
                "status-code": status[1]
            }
        }
        if status[2]:
            header["status"]["reason"] = status[2]
        for header_line in header_lines[1:]:
            with suppress(ValueError):
                field, value = header_line.split(": ")
                header[field] = value
        return header

    def parse_chunked_body(raw_body: str) -> str:
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
        raw_header, raw_body = re.split(r"\n\n|\r\n\r\n", response, maxsplit=1)
        header = cls.parse_header(raw_header)
        if header.get("Transfer-Encoding") == "chunked":
            body = cls.parse_chunked_body(raw_body)
        else:
            body = raw_body
        return header, body

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
    def parse_assertions(body: str) -> dict:
        parts = re.split(r"\n\n|\r\n\r\n", body)
        try:
            return [yaml.safe_load(part) for part in parts[:-1]]
        except yaml.YAMLError as error:
            raise SnapdAPIError(
                f"Unable to parse application/x.ubuntu.assertion content: {body}"
            ) from error

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
        header, body = self.parse(response.stdout)
        status = header["status"]
        if status["status-code"] != "200":
            try:
                reason_message = f" ({status['reason']})"
            except KeyError:
                reason_message = ""
            raise SnapdAPIError(
                f"Response {status['code']}{reason_message} to request {url}"
            )
        content_type = header.get("Content-Type")
        if content_type == "application/json":
            return self.parse_json(body)["result"]
        if content_type == "application/x.ubuntu.assertion":
            return self.parse_assertions(body)
        raise SnapdAPIError(f"Unable to parse content type: {content_type}")
