from io import StringIO
import json
import re
from urllib.parse import urlencode

from toolbox.devices import Device


class SnapdAPIClient:
    def __init__(self, device: Device):
        self.device = device

    def create_get_request(self, endpoint: str, params: dict = None) -> str:
        query = "?" + urlencode(params, doseq=True) if params else ""
        return (
            f"GET /v2/{endpoint}{query} "
            "HTTP/1.1\n"
            "Host: placeholder\n"
            "Connection: close\n\n"
        )

    def get(self, endpoint: str, params: dict = None) -> dict:
        request = self.create_get_request(endpoint, params)
        raw_response = self.device.run(
            ["nc", "-U", "/run/snapd.socket"],
            in_stream=StringIO(request),
            echo_stdin=False,
            hide=True,
        ).stdout
        match = re.search(r"{.*}", raw_response, re.DOTALL)
        try:
            response_data = match.group(0)
        except AttributeError as error:
            raise RuntimeError(f"Unexpected response {raw_response}") from error
        return json.loads(response_data)
