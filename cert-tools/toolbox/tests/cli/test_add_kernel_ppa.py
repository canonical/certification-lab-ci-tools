"""Tests for the add-kernel-ppa CLI."""

import json

import pytest

from toolbox.cli import add_kernel_ppa


@pytest.fixture(autouse=True)
def package_data_map(monkeypatch):
    package_data_map = {
        "cert-package-data": None,
        "cert-package-data-proposed2": (
            "https://ppa.launchpadcontent.net/canonical-kernel-team/proposed2/ubuntu"
        ),
        "cert-realtime-package-data": (
            "https://private-ppa.launchpadcontent.net/ubuntu-advantage/"
            "realtime-proposed/ubuntu"
        ),
    }
    monkeypatch.setattr(add_kernel_ppa, "PACKAGE_DATA_MAP", package_data_map)
    monkeypatch.setenv("PACKAGE_DATA_MAP", "defined")


def test_package_data_to_ppa_data_uses_archive_proposed(mocker, monkeypatch):
    monkeypatch.setenv("SOURCE_PACKAGE_DATA", "cert-package-data")
    proposed_repository = mocker.patch.object(
        add_kernel_ppa, "proposed_repository", return_value="proposed-url"
    )

    result = add_kernel_ppa.package_data_to_ppa_data("arm64")

    proposed_repository.assert_called_once_with("arm64")
    assert result == add_kernel_ppa.PPAData("proposed-url", None, None, None, False)


@pytest.mark.parametrize(
    "package_data, credentials_suffix",
    [
        ("cert-package-data-proposed2", "CERT_PACKAGE_DATA_PROPOSED2"),
        ("cert-realtime-package-data", "CERT_REALTIME_PACKAGE_DATA"),
    ],
)
def test_package_data_to_ppa_data_uses_package_specific_credentials(
    monkeypatch, package_data, credentials_suffix
):
    monkeypatch.setenv("SOURCE_PACKAGE_DATA", package_data)
    monkeypatch.setenv(f"KERNEL_PPA_USERNAME_{credentials_suffix}", "username")
    monkeypatch.setenv(f"KERNEL_PPA_PASSWORD_{credentials_suffix}", "password")
    monkeypatch.setenv(f"KERNEL_PPA_KEY_{credentials_suffix}", "12345678")

    result = add_kernel_ppa.package_data_to_ppa_data("amd64")

    assert result == add_kernel_ppa.PPAData(
        add_kernel_ppa.PACKAGE_DATA_MAP[package_data],
        "username",
        "password",
        "12345678",
        True,
    )


def test_discover_public_ppa_key(mocker):
    device = mocker.Mock()
    device.run.return_value.stdout = json.dumps(
        {"signing_key_fingerprint": "D8027DCFBDAF61FB44D5FDCE9B5F34077FA4288A"}
    )

    key = add_kernel_ppa.discover_public_ppa_key(
        device,
        "https://ppa.launchpadcontent.net/canonical-kernel-team/proposed2/ubuntu",
    )

    assert key == "D8027DCFBDAF61FB44D5FDCE9B5F34077FA4288A"
    device.run.assert_called_once_with(
        [
            "wget",
            "-qO-",
            (
                "https://api.launchpad.net/1.0/~canonical-kernel-team/"
                "+archive/ubuntu/proposed2"
            ),
        ],
        hide=True,
    )


def test_enable_public_ppa_discovers_and_installs_key(mocker):
    device = mocker.Mock()
    discover_key = mocker.patch.object(
        add_kernel_ppa, "discover_public_ppa_key", return_value="12345678"
    )
    add_key = mocker.patch.object(
        add_kernel_ppa,
        "add_ppa_key",
        return_value="/etc/apt/keyrings/12345678.gpg",
    )
    ppa_data = add_kernel_ppa.PPAData(
        "https://ppa.launchpadcontent.net/canonical-kernel-team/proposed2/ubuntu",
        None,
        None,
        None,
        True,
    )

    add_kernel_ppa.enable_ppa(device, ppa_data, "noble")

    discover_key.assert_called_once_with(device, ppa_data.url)
    add_key.assert_called_once_with(device, "12345678")
    assert device.write_remote_file.call_args_list == [
        mocker.call(
            "/etc/apt/sources.list.d/canonical-kernel-team-proposed2-ubuntu.list",
            "deb [signed-by=/etc/apt/keyrings/12345678.gpg] "
            f"{ppa_data.url} noble main\n",
        ),
        mocker.call(
            "/etc/apt/preferences.d/pining",
            "Package: *\nPin: release o=Ubuntu,a=noble\nPin-Priority: 500\n",
        ),
    ]


def test_enable_private_ppa_writes_credentials(mocker):
    device = mocker.Mock()
    add_key = mocker.patch.object(
        add_kernel_ppa,
        "add_ppa_key",
        return_value="/etc/apt/keyrings/12345678.gpg",
    )
    ppa_data = add_kernel_ppa.PPAData(
        "https://private-ppa.launchpadcontent.net/team/archive/ubuntu",
        "username",
        "password",
        "12345678",
        True,
    )

    add_kernel_ppa.enable_ppa(device, ppa_data, "noble")

    add_key.assert_called_once_with(device, "12345678")
    assert device.write_remote_file.call_args_list[0] == mocker.call(
        "/etc/apt/auth.conf.d/ppa-team-archive-ubuntu.conf",
        "\nmachine private-ppa.launchpadcontent.net/team/archive/ubuntu\n"
        "login username\npassword password\n",
    )
    device.run.assert_called_once_with(
        [
            "sudo",
            "chmod",
            "0600",
            "/etc/apt/auth.conf.d/ppa-team-archive-ubuntu.conf",
        ]
    )


def test_enable_private_ppa_requires_credentials(mocker):
    device = mocker.Mock()
    ppa_data = add_kernel_ppa.PPAData(
        "https://private-ppa.launchpadcontent.net/team/archive/ubuntu",
        None,
        None,
        "12345678",
        True,
    )

    with pytest.raises(SystemExit, match="Private PPA credentials are required"):
        add_kernel_ppa.enable_ppa(device, ppa_data, "noble")


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
    status.wait_for_status.return_value = True
    mocker.patch.object(add_kernel_ppa, "LabDevice", return_value=device)
    mocker.patch("sys.argv", ["add-kernel-ppa", "amd64", "noble"])
    return device


def test_main_uses_archive_proposed_by_default(mocker, monkeypatch, main_device):
    monkeypatch.delenv("SOURCE_PACKAGE_DATA", raising=False)
    proposed_repository = mocker.patch.object(
        add_kernel_ppa, "proposed_repository", return_value="proposed-url"
    )
    enable_archive = mocker.patch.object(add_kernel_ppa, "enable_archive_proposed")

    add_kernel_ppa.main()

    proposed_repository.assert_called_once_with("amd64")
    enable_archive.assert_called_once_with(
        main_device,
        add_kernel_ppa.PPAData("proposed-url", None, None, None, False),
        "noble",
    )


def test_main_enables_public_ppa_without_credentials(mocker, monkeypatch, main_device):
    monkeypatch.setenv("SOURCE_PACKAGE_DATA", "cert-package-data-proposed2")
    enable_ppa = mocker.patch.object(add_kernel_ppa, "enable_ppa")

    add_kernel_ppa.main()

    enable_ppa.assert_called_once_with(
        main_device,
        add_kernel_ppa.PPAData(
            add_kernel_ppa.PACKAGE_DATA_MAP["cert-package-data-proposed2"],
            None,
            None,
            None,
            True,
        ),
        "noble",
    )


def test_main_updates_and_installs_kernel_from_private_ppa(
    mocker, monkeypatch, main_device
):
    monkeypatch.setenv("SOURCE_PACKAGE_DATA", "cert-realtime-package-data")
    monkeypatch.setenv("KERNEL_PPA_USERNAME_CERT_REALTIME_PACKAGE_DATA", "username")
    monkeypatch.setenv("KERNEL_PPA_PASSWORD_CERT_REALTIME_PACKAGE_DATA", "password")
    monkeypatch.setenv("KERNEL_PPA_KEY_CERT_REALTIME_PACKAGE_DATA", "12345678")
    monkeypatch.setenv("CONCRETE_KERNEL", "linux-image-test")
    enable_ppa = mocker.patch.object(add_kernel_ppa, "enable_ppa")
    debs = main_device.interfaces[add_kernel_ppa.DebInterface]
    debs.update.return_value = True
    debs.install.return_value = True

    add_kernel_ppa.main()

    ppa_data = add_kernel_ppa.PPAData(
        add_kernel_ppa.PACKAGE_DATA_MAP["cert-realtime-package-data"],
        "username",
        "password",
        "12345678",
        True,
    )
    enable_ppa.assert_called_once_with(main_device, ppa_data, "noble")
    debs.update.assert_called_once_with()
    debs.install.assert_called_once_with(["linux-image-test"])
