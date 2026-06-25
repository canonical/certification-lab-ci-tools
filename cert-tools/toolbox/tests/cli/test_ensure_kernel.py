"""Tests for the ensure-kernel CLI."""

import pytest
from invoke import Result

from toolbox.cli import ensure_kernel
from toolbox.cli.ensure_kernel import (
    booted_expected_kernel,
    main,
    parse_booted_version,
)


@pytest.mark.parametrize(
    "signature, expected",
    [
        ("Ubuntu 6.8.0-130.130-generic 6.8.12", "6.8.0-130.130-generic"),
        ("", ""),
        ("Ubuntu", ""),
    ],
)
def test_parse_booted_version(signature, expected):
    assert parse_booted_version(signature) == expected


@pytest.mark.parametrize(
    "booted_version_flavour, expected_version, expected",
    [
        ("6.8.0-130.130-generic", "6.8.0-130.130", True),
        ("6.8.0-131.131-generic", "6.8.0-130.130", False),
        # "6.8.0-130.13" must not match "6.8.0-130.130-generic": the trailing
        # dash in the expected prefix guards against partial-number matches.
        ("6.8.0-130.130-generic", "6.8.0-130.13", False),
    ],
)
def test_booted_expected_kernel(booted_version_flavour, expected_version, expected):
    assert booted_expected_kernel(booted_version_flavour, expected_version) is expected


def _patch_device(mocker, result):
    device = mocker.Mock()
    device.host = "10.0.0.1"
    device.run.return_value = result
    mocker.patch.object(ensure_kernel, "LabDevice", return_value=device)
    return device


def test_main_success(mocker, capsys):
    result = Result(stdout="Ubuntu 6.8.0-130.130-generic 6.8.12\n", exited=0)
    device = _patch_device(mocker, result)
    mocker.patch("sys.argv", ["ensure-kernel", "6.8.0-130.130"])

    main()

    device.run.assert_called_once_with("cat /proc/version_signature")
    out = capsys.readouterr().out
    assert "Kernel verification OK" in out


def test_main_mismatch_exits_nonzero(mocker, capsys):
    result = Result(stdout="Ubuntu 6.8.0-131.131-generic 6.8.12\n", exited=0)
    _patch_device(mocker, result)
    mocker.patch("sys.argv", ["ensure-kernel", "6.8.0-130.130"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    assert "does not match the expected version" in capsys.readouterr().out


def test_main_empty_signature_exits_nonzero(mocker, capsys):
    result = Result(stdout="\n", exited=0)
    _patch_device(mocker, result)
    mocker.patch("sys.argv", ["ensure-kernel", "6.8.0-130.130"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    assert "could not determine the booted kernel version" in (capsys.readouterr().out)


def test_main_read_failure_exits_nonzero(mocker, capsys):
    result = Result(stderr="No such file or directory\n", exited=1)
    _patch_device(mocker, result)
    mocker.patch("sys.argv", ["ensure-kernel", "6.8.0-130.130"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    assert "could not read /proc/version_signature" in capsys.readouterr().out
