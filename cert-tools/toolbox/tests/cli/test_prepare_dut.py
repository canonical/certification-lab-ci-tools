"""Tests for preparing the device under test."""

import os

import pytest
from invoke import Result

from toolbox.cli import prepare_dut as cli


@pytest.fixture
def scriptlets_dir(tmp_path):
    return str(tmp_path)


@pytest.fixture
def device(mocker):
    device = mocker.Mock(host="dut")
    device.run.return_value = Result(exited=0)
    device.put.return_value = Result(stdout=".scriptlets/retry", exited=0)
    mocker.patch.object(cli, "LabDevice", return_value=device)
    return device


@pytest.fixture
def environment(monkeypatch, scriptlets_dir):
    monkeypatch.setenv("SCRIPTLETS_PATH", scriptlets_dir)
    monkeypatch.setenv("TOOLS_PATH_DEVICE", ".scriptlets")
    monkeypatch.setattr("sys.argv", ["prepare-dut"])


def run(monkeypatch, *args):
    monkeypatch.setattr("sys.argv", ["prepare-dut", *args])
    cli.main()


def test_copies_scriptlets_from_environment_paths(
    device, environment, scriptlets_dir, capsys
):
    cli.main()

    device.run.assert_called_once_with(["mkdir", "-p", ".scriptlets"], hide=True)
    device.put.assert_called_once_with(
        local_paths=[
            os.path.join(scriptlets_dir, name) for name in cli.DEVICE_SCRIPTLETS
        ],
        remote_dir=".scriptlets",
    )
    assert ".scriptlets/retry" in capsys.readouterr().out


def test_arguments_override_environment(device, environment, monkeypatch, tmp_path):
    other_dir = tmp_path / "other"
    other_dir.mkdir()

    run(monkeypatch, "--local-path", str(other_dir), "--remote-path", "tools")

    device.run.assert_called_once_with(["mkdir", "-p", "tools"], hide=True)
    local_paths = device.put.call_args.kwargs["local_paths"]
    assert all(path.startswith(str(other_dir)) for path in local_paths)
    assert device.put.call_args.kwargs["remote_dir"] == "tools"


def test_directory_is_created_before_copying(device, environment, mocker):
    manager = mocker.Mock()
    manager.attach_mock(device.run, "run")
    manager.attach_mock(device.put, "put")

    cli.main()

    assert [call[0] for call in manager.mock_calls] == ["run", "put"]


@pytest.mark.parametrize(
    "variable, message",
    [
        ("SCRIPTLETS_PATH", "local-path is not specified"),
        ("TOOLS_PATH_DEVICE", "remote-path is not specified"),
    ],
)
def test_missing_path_is_fatal(device, environment, monkeypatch, variable, message):
    monkeypatch.delenv(variable)

    with pytest.raises(SystemExit, match=message):
        cli.main()

    cli.LabDevice.assert_not_called()


def test_local_path_must_be_a_directory(device, environment, monkeypatch, tmp_path):
    missing = tmp_path / "missing"

    with pytest.raises(SystemExit, match="is not a directory"):
        run(monkeypatch, "--local-path", str(missing))

    cli.LabDevice.assert_not_called()


def test_missing_device_is_fatal(environment, mocker):
    mocker.patch.object(
        cli, "LabDevice", side_effect=RuntimeError("DEVICE_IP is not set")
    )

    with pytest.raises(SystemExit, match="DEVICE_IP is not set"):
        cli.main()


def test_directory_creation_failure_does_not_copy(device, environment):
    device.run.return_value = Result(exited=1, stderr="Permission denied\n")

    with pytest.raises(SystemExit, match="could not create.*Permission denied"):
        cli.main()

    device.put.assert_not_called()


def test_copy_failure_is_fatal(device, environment):
    device.put.return_value = Result(exited=255, stderr="No such file: retry\n")

    with pytest.raises(SystemExit, match="could not copy.*No such file: retry"):
        cli.main()
