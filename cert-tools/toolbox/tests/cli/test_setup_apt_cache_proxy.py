"""Tests for the setup_apt_cache_proxy CLI."""

import pytest
from invoke import Result

from toolbox.cli import setup_apt_cache_proxy
from toolbox.cli.setup_apt_cache_proxy import (
    DEFAULT_DIRECT_HOSTS,
    direct_hosts_from_env,
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


def test_generate_proxy_config_pins_the_repositories_the_cache_cannot_serve():
    """dl.google.com and the CUDA repository must be fetched by the DUT itself.

    The cache is HTTP-only, so it cannot follow their redirect to HTTPS, and it
    cannot reach them at all; APT keys proxy exceptions by host, so this is the
    only granularity available.
    """
    config = generate_proxy_config("example.com")
    assert 'Acquire::http::Proxy::dl.google.com "DIRECT";' in config
    assert 'Acquire::http::Proxy::developer.download.nvidia.com "DIRECT";' in config
    assert config.count("\n") == 2 + len(DEFAULT_DIRECT_HOSTS)


def test_generate_proxy_config_accepts_an_explicit_exception_list():
    config = generate_proxy_config("example.com", direct_hosts=["only.example.com"])
    assert 'Acquire::http::Proxy::only.example.com "DIRECT";' in config
    assert "dl.google.com" not in config
    assert config.count("\n") == 3


def test_generate_proxy_config_can_omit_exceptions_entirely():
    config = generate_proxy_config("example.com", direct_hosts=())
    assert config.count("\n") == 2
    assert "Proxy::" not in config


def test_direct_hosts_from_env_defaults_to_the_shipped_list():
    assert direct_hosts_from_env(None) == DEFAULT_DIRECT_HOSTS


def test_direct_hosts_from_env_parses_a_list_and_allows_disabling():
    assert direct_hosts_from_env("a.example, b.example ") == (
        "a.example",
        "b.example",
    )
    assert direct_hosts_from_env("") == ()


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


def test_main_writes_the_direct_exceptions(mocker, capsys, monkeypatch):
    """The exceptions must reach the file the DUT actually reads."""
    os_result = Result(stdout="ubuntu\n", exited=0)
    write_result = Result(stdout="", exited=0)
    device = _patch_device(mocker, os_result, write_result)

    main()

    written = next(
        call.kwargs["in_stream"].getvalue()
        for call in device.run.call_args_list
        if "in_stream" in call.kwargs
    )
    assert 'Acquire::http::Proxy "http://tel-apt-cache.canonical.com:3142";' in written
    assert 'Acquire::https::Proxy "DIRECT";' in written
    assert 'Acquire::http::Proxy::dl.google.com "DIRECT";' in written
    assert 'Acquire::http::Proxy::developer.download.nvidia.com "DIRECT";' in written


def test_main_honours_an_override_of_the_exception_list(mocker, capsys, monkeypatch):
    monkeypatch.setenv("APT_CACHE_DIRECT_HOSTS", "only.example.com")
    os_result = Result(stdout="ubuntu\n", exited=0)
    write_result = Result(stdout="", exited=0)
    device = _patch_device(mocker, os_result, write_result)

    main()

    written = next(
        call.kwargs["in_stream"].getvalue()
        for call in device.run.call_args_list
        if "in_stream" in call.kwargs
    )
    assert 'Acquire::http::Proxy::only.example.com "DIRECT";' in written
    assert "dl.google.com" not in written


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
    write_result = Result(
        stdout="something went wrong\n", exited=1, stderr="Permission denied\n"
    )
    _patch_device(mocker, os_result, write_result)

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "ERROR: Failed to write proxy config" in out


@pytest.fixture(autouse=True)
def default_argv(monkeypatch):
    monkeypatch.setattr("sys.argv", ["setup_apt_cache_proxy"])


def test_main_explicit_enable(mocker, capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["setup_apt_cache_proxy", "enable"])
    os_result = Result(stdout="ubuntu\n", exited=0)
    write_result = Result(stdout="", exited=0)
    device = _patch_device(mocker, os_result, write_result)

    main()

    assert "tee" in device.run.call_args_list[1].args[0]
    assert "Setting up apt-cache proxy" in capsys.readouterr().out


def test_main_disable_success(mocker, capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["setup_apt_cache_proxy", "disable"])
    os_result = Result(stdout="ubuntu\n", exited=0)
    remove_result = Result(stdout="", exited=0)
    device = _patch_device(mocker, os_result, remove_result)

    main()

    assert device.run.call_args_list[1].args[0] == (
        "sudo rm -f /etc/apt/apt.conf.d/02proxy"
    )
    out = capsys.readouterr().out
    assert "Removing apt-cache proxy configuration" in out
    assert "Done." in out


def test_main_disable_failure_skips(mocker, capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["setup_apt_cache_proxy", "disable"])
    os_result = Result(stdout="ubuntu\n", exited=0)
    remove_result = Result(stdout="", exited=1, stderr="Permission denied\n")
    _patch_device(mocker, os_result, remove_result)

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    assert "ERROR: Failed to remove proxy config" in capsys.readouterr().out


def test_main_disable_ubuntu_core_skips(mocker, capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["setup_apt_cache_proxy", "disable"])
    os_result = Result(stdout="ubuntu-core\n", exited=0)
    device = _patch_device(mocker, os_result)

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    assert device.run.call_count == 1
    assert "SKIP: Ubuntu Core detected" in capsys.readouterr().out


def test_main_invalid_action_exits_nonzero(mocker, monkeypatch):
    monkeypatch.setattr("sys.argv", ["setup_apt_cache_proxy", "bogus"])
    mocker.patch.object(setup_apt_cache_proxy, "LabDevice")

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 2


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
