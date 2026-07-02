"""Tests for the setup_apt_cache_proxy CLI."""

import pytest
from invoke import Result

from toolbox.cli import setup_apt_cache_proxy
from toolbox.cli.setup_apt_cache_proxy import (
    generate_proxy_config,
    is_ubuntu_core,
    main,
)


# ---------------------------------------------------------------------------
# generate_proxy_config
# ---------------------------------------------------------------------------

def test_generate_proxy_config_default():
    config = generate_proxy_config("tel-apt-cache.canonical.com")
    assert 'Acquire::http::Proxy "http://tel-apt-cache.canonical.com:3142";' in config
    assert 'Acquire::https::Proxy "DIRECT";' in config


def test_generate_proxy_config_custom_host():
    config = generate_proxy_config("10.102.155.30")
    assert 'Acquire::http::Proxy "http://10.102.155.30:3142";' in config
    assert 'Acquire::https::Proxy "DIRECT";' in config


def test_generate_proxy_config_produces_two_lines():
    config = generate_proxy_config("example.com")
    assert config.count("\n") == 2


# ---------------------------------------------------------------------------
# is_ubuntu_core
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "os_id, expected",
    [
        ("ubuntu-core", True),
        ("ubuntu", False),
        (" ubuntu-core ", True),
        ("", False),
        ("ubuntu-core-extra", False),
    ],
)
def test_is_ubuntu_core(os_id, expected):
    assert is_ubuntu_core(os_id) is expected


# ---------------------------------------------------------------------------
# main — helpers
# ---------------------------------------------------------------------------

def _patch_device(mocker, os_result, write_result=None):
    """Patch LabDevice so that device.run returns controlled results.

    The first call returns ``os_result`` (OS detection) and the second
    call returns ``write_result`` (proxy config write).
    """
    device = mocker.Mock()
    device.host = "10.0.0.1"
    if write_result is not None:
        device.run.side_effect = [os_result, write_result]
    else:
        device.run.side_effect = [os_result]
    mocker.patch.object(setup_apt_cache_proxy, "LabDevice", return_value=device)
    return device


# ---------------------------------------------------------------------------
# main — success path
# ---------------------------------------------------------------------------

def test_main_success(mocker, capsys):
    os_result = Result(stdout="ubuntu\n", exited=0)
    write_result = Result(stdout="", exited=0)
    _patch_device(mocker, os_result, write_result)

    main()

    out = capsys.readouterr().out
    assert "Setting up apt-cache proxy" in out
    assert "Done." in out


def test_main_uses_custom_cache_host_from_env(mocker, capsys, monkeypatch):
    monkeypatch.setenv("APT_CACHE_HOST", "my-cache.example.com")
    os_result = Result(stdout="ubuntu\n", exited=0)
    write_result = Result(stdout="", exited=0)
    _patch_device(mocker, os_result, write_result)

    main()

    out = capsys.readouterr().out
    assert "my-cache.example.com" in out


# ---------------------------------------------------------------------------
# main — Ubuntu Core skip
# ---------------------------------------------------------------------------

def test_main_ubuntu_core_skips(mocker, capsys):
    os_result = Result(stdout="ubuntu-core\n", exited=0)
    _patch_device(mocker, os_result)

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "SKIP: Ubuntu Core detected" in out


# ---------------------------------------------------------------------------
# main — OS detection failure skip
# ---------------------------------------------------------------------------

def test_main_os_detection_failure_skips(mocker, capsys):
    os_result = Result(stdout="", exited=255, stderr="Connection refused\n")
    _patch_device(mocker, os_result)

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "SKIP: Failed to detect OS" in out
    assert "255" in out


# ---------------------------------------------------------------------------
# main — write failure skip
# ---------------------------------------------------------------------------

def test_main_write_failure_skips(mocker, capsys):
    os_result = Result(stdout="ubuntu\n", exited=0)
    write_result = Result(stdout="something went wrong\n", exited=1, stderr="Permission denied\n")
    _patch_device(mocker, os_result, write_result)

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "ERROR: Failed to write proxy config" in out


# ---------------------------------------------------------------------------
# main — no DEVICE_IP
# ---------------------------------------------------------------------------

def test_main_no_device_ip_exits_nonzero(mocker, capsys, monkeypatch):
    monkeypatch.delenv("DEVICE_IP", raising=False)
    mocker.patch.object(
        setup_apt_cache_proxy,
        "LabDevice",
        side_effect=RuntimeError("Host is unspecified and 'DEVICE_IP' is not set"),
    )

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    assert "ERROR:" in capsys.readouterr().out
