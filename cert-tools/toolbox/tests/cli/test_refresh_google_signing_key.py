"""Tests for downloading and safely installing Google's APT signing key."""

import io
import subprocess
from urllib.error import URLError

import pytest
from invoke import Result

from toolbox.cli import refresh_google_signing_key as cli

KEY = b"-----BEGIN PGP PUBLIC KEY BLOCK-----\nexample\n-----END PGP PUBLIC KEY BLOCK-----\n"


def setup_download(mocker, payload=KEY):
    device = mocker.Mock(host="dut")
    device.run.return_value = Result(exited=0)
    mocker.patch.object(cli, "LabDevice", return_value=device)
    download = mocker.patch.object(cli, "urlopen")
    download.return_value.__enter__.return_value = io.BytesIO(payload)
    return device, download


def test_refresh_transfers_download_to_dut(mocker):
    device, download = setup_download(mocker)
    cli.main()
    download.assert_called_once_with(cli.KEY_URL, timeout=30)
    device.run.assert_called_once()
    assert device.run.call_args.kwargs["in_stream"].read() == KEY.decode("ascii")


def test_download_failure_does_not_write_key(mocker):
    device, download = setup_download(mocker)
    download.side_effect = URLError("connection failed")
    with pytest.raises(SystemExit, match="Failed to download"):
        cli.main()
    device.run.assert_not_called()


@pytest.mark.parametrize("payload", [b"", b"<html>error</html>", b"\xff"])
def test_invalid_download_does_not_write_key(mocker, payload):
    device, _ = setup_download(mocker, payload)
    with pytest.raises(SystemExit):
        cli.main()
    device.run.assert_not_called()


def test_remote_failure_is_fatal(mocker):
    device, _ = setup_download(mocker)
    device.run.return_value = Result(exited=255, stderr="Connection refused")
    with pytest.raises(SystemExit, match="Failed to install.*Connection refused"):
        cli.main()


def test_missing_device_is_fatal(mocker):
    mocker.patch.object(
        cli, "LabDevice", side_effect=RuntimeError("DEVICE_IP is not set")
    )
    download = mocker.patch.object(cli, "urlopen")
    with pytest.raises(SystemExit, match="DEVICE_IP is not set"):
        cli.main()
    download.assert_not_called()


def test_install_replaces_key_with_readable_permissions(tmp_path):
    destination = tmp_path / "google.asc"
    destination.write_text("old key")
    command = cli.INSTALL_KEY.replace(cli.KEY_PATH, str(destination))
    result = subprocess.run(
        ["sh", "-c", command], input=KEY, capture_output=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert destination.read_bytes() == KEY
    assert destination.stat().st_mode & 0o777 == 0o644
    assert list(tmp_path.iterdir()) == [destination]


def test_failed_write_preserves_previous_key(tmp_path):
    destination = tmp_path / "google.asc"
    destination.write_text("old key")
    # Simulate cat writing partial input and then failing, e.g. a full disk.
    command = cli.INSTALL_KEY.replace(cli.KEY_PATH, str(destination))
    command = "cat() { printf partial; return 1; }\n" + command
    result = subprocess.run(
        ["sh", "-c", command], input=KEY, capture_output=True, check=False
    )
    assert result.returncode != 0
    assert destination.read_text() == "old key"
    assert list(tmp_path.iterdir()) == [destination]
