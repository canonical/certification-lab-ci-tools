"""Tests for the add-kernel-ppa CLI."""

from pathlib import Path

import pytest

from toolbox.cli import add_kernel_ppa


def test_package_data_to_ppa_data_uses_archive_proposed(mocker, monkeypatch):
    monkeypatch.setenv("SOURCE_PACKAGE_DATA", "cert-package-data")
    proposed_repository = mocker.patch.object(
        add_kernel_ppa, "proposed_repository", return_value="proposed-url"
    )

    result = add_kernel_ppa.package_data_to_ppa_data("arm64")

    proposed_repository.assert_called_once_with("arm64")
    assert result == add_kernel_ppa.PPAData("proposed-url", None, None, None)


@pytest.mark.parametrize(
    "package_data, suffix",
    [
        ("cert-package-data-proposed2", "2"),
        ("cert-realtime-package-data", ""),
    ],
)
def test_package_data_to_ppa_data_uses_credential_suffix(
    monkeypatch, package_data, suffix
):
    monkeypatch.setenv("SOURCE_PACKAGE_DATA", package_data)
    monkeypatch.setenv(f"KERNEL_PPA_USERNAME{suffix}", "username")
    monkeypatch.setenv(f"KERNEL_PPA_PASSWORD{suffix}", "password")
    monkeypatch.setenv(f"KERNEL_PPA_KEY{suffix}", "key")

    result = add_kernel_ppa.package_data_to_ppa_data("amd64")

    assert result == add_kernel_ppa.PPAData(
        add_kernel_ppa.PACKAGE_DATA_MAP[package_data],
        "username",
        "password",
        "key",
    )


@pytest.fixture
def main_device(mocker):
    device = mocker.Mock()
    device.interfaces = mocker.MagicMock()
    debs = mocker.Mock()
    reboot = mocker.Mock()
    status = mocker.Mock()
    device.interfaces.__getitem__.side_effect = {
        add_kernel_ppa.DebInterface: debs,
        add_kernel_ppa.RebootInterface: reboot,
        add_kernel_ppa.SystemStatusInterface: status,
    }.__getitem__
    debs.update.return_value = True
    debs.upgrade.return_value = True
    status.wait_for_status.return_value = True
    mocker.patch.object(add_kernel_ppa, "LabDevice", return_value=device)
    mocker.patch("sys.argv", ["add-kernel-ppa", "amd64", "noble"])
    return device, debs


def test_main_uses_archive_proposed_by_default(mocker, monkeypatch, main_device):
    device, _ = main_device
    monkeypatch.delenv("SOURCE_PACKAGE_DATA", raising=False)
    proposed_repository = mocker.patch.object(
        add_kernel_ppa, "proposed_repository", return_value="proposed-url"
    )
    enable_archive_proposed = mocker.patch.object(
        add_kernel_ppa, "enable_archive_proposed"
    )

    add_kernel_ppa.main()

    proposed_repository.assert_called_once_with("amd64")
    enable_archive_proposed.assert_called_once_with(device, "proposed-url", "noble")


def test_main_calls_legacy_script_for_authenticated_ppa(
    mocker, monkeypatch, main_device
):
    device, debs = main_device
    monkeypatch.setenv("TOOLS_PATH", "/tools")
    monkeypatch.setenv("CONCRETE_KERNEL", "linux-image-test")
    mocker.patch.object(
        add_kernel_ppa,
        "package_data_to_ppa_data",
        return_value=add_kernel_ppa.PPAData(
            "private-url", "username", "password", "key"
        ),
    )
    check_call = mocker.patch.object(add_kernel_ppa.subprocess, "check_call")

    add_kernel_ppa.main()

    check_call.assert_called_once_with(
        [
            "_put",
            Path("/tools/add_private_ppa.py"),
            Path("/tools/kernel-switcher.py"),
            ":",
        ]
    )
    device.run.assert_called_once_with(
        [
            "sudo",
            "./add_private_ppa.py",
            "private-url",
            "username",
            "password",
            "key",
        ]
    )
    assert debs.update.call_count == 2
    debs.install.assert_called_once_with("linux-image-test")
