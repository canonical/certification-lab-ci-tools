"""Tests for CheckboxSnapsInstaller."""

import os

import pytest
from invoke import Result

from toolbox.checkbox.installers.snaps import CheckboxSnapsInstaller
from toolbox.entities.channels import Channel
from toolbox.entities.connections import SnapConnection
from toolbox.entities.snaps import SnapSpecifier
from toolbox.interfaces.reboot import RebootInterface
from toolbox.interfaces.snapd import SnapdAPIClient
from toolbox.interfaces.snaps import SnapInterface, SnapInstallError
from toolbox.interfaces.status import SystemStatusInterface
from tests.devices.trivial import TrivialDevice


class TestCheckboxSnapsInstaller:
    """Tests for CheckboxSnapsInstaller."""

    @pytest.mark.parametrize(
        "system_store,model_store,expected_store",
        [
            (None, "branded-store", "branded-store"),
            ("system-store", None, "system-store"),
            ("system-store", "branded-store", "branded-store"),
        ],
    )
    def test_init_store_selection(
        self, mocker, system_store, model_store, expected_store
    ):
        """Test initialization selects correct store from model or system."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                RebootInterface(),
                SystemStatusInterface(),
                SnapInterface(),
            ]
        )
        agent = TrivialDevice()

        mock_snapd = device.interfaces[SnapdAPIClient]
        mocker.patch.object(
            mock_snapd,
            "get",
            side_effect=[
                {"architecture": "amd64", "store": system_store},  # system-info
                [{"store": model_store} if model_store else {}],  # model
            ],
        )

        mock_runtime = SnapSpecifier(
            name="checkbox22", channel=Channel.from_string("latest/stable")
        )
        mocker.patch(
            "toolbox.checkbox.installers.snaps.CheckboxRuntimeHelper"
        ).return_value.determine_checkbox_runtime.return_value = mock_runtime

        frontends = [
            SnapSpecifier(name="checkbox", channel=Channel.from_string("22/stable"))
        ]
        mock_snapstore = mocker.Mock()

        installer = CheckboxSnapsInstaller(device, agent, frontends, mock_snapstore)

        assert installer.store == expected_store

    def test_init_creates_connector_with_predicates(self, mocker):
        """Test initialization creates SnapConnector with predicates."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                RebootInterface(),
                SystemStatusInterface(),
                SnapInterface(),
            ]
        )

        mocker.patch.object(
            device.interfaces[SnapdAPIClient],
            "get",
            side_effect=[
                {"architecture": "amd64", "store": None},
                [{"store": "branded"}],
            ],
        )
        mocker.patch(
            "toolbox.checkbox.installers.snaps.CheckboxRuntimeHelper"
        ).return_value.determine_checkbox_runtime.return_value = SnapSpecifier(
            name="checkbox22", channel=Channel.from_string("latest/stable")
        )

        mock_connector_class = mocker.patch(
            "toolbox.checkbox.installers.snaps.SnapConnector"
        )
        mock_predicate = mocker.Mock()

        frontends = [
            SnapSpecifier(name="checkbox", channel=Channel.from_string("22/stable"))
        ]

        CheckboxSnapsInstaller(
            device,
            TrivialDevice(),
            frontends,
            mocker.Mock(),
            predicates=[mock_predicate],
        )

        # Verify connector was created with SelectSnaps + custom predicates
        mock_connector_class.assert_called_once()
        predicates_arg = mock_connector_class.call_args[1]["predicates"]
        assert len(predicates_arg) == 2  # SelectSnaps + custom predicate
        assert predicates_arg[1] is mock_predicate

    def test_checkbox_cli_property(self, mocker):
        """Test checkbox_cli property returns correct command."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                RebootInterface(),
                SystemStatusInterface(),
                SnapInterface(),
            ]
        )
        mocker.patch.object(
            device.interfaces[SnapdAPIClient],
            "get",
            side_effect=[
                {"architecture": "amd64", "store": None},
                [{"store": "branded"}],
            ],
        )

        mocker.patch(
            "toolbox.checkbox.installers.snaps.CheckboxRuntimeHelper"
        ).return_value.determine_checkbox_runtime.return_value = SnapSpecifier(
            name="checkbox22", channel=Channel.from_string("latest/stable")
        )

        frontends = [
            SnapSpecifier(name="my-checkbox", channel=Channel.from_string("22/stable"))
        ]

        installer = CheckboxSnapsInstaller(
            device, TrivialDevice(), frontends, mocker.Mock()
        )

        assert installer.checkbox_cli == "my-checkbox.checkbox-cli"

    def test_install_frontend_snap_devmode_success(self, mocker):
        """Test installing frontend snap successfully with devmode."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                RebootInterface(),
                SystemStatusInterface(),
                SnapInterface(),
            ]
        )
        device.run = mocker.Mock(return_value=Result(stdout="", exited=0))

        mocker.patch.object(
            device.interfaces[SnapdAPIClient],
            "get",
            side_effect=[
                {"architecture": "amd64", "store": None},
                [{"store": "branded"}],
            ],
        )
        mocker.patch(
            "toolbox.checkbox.installers.snaps.CheckboxRuntimeHelper"
        ).return_value.determine_checkbox_runtime.return_value = SnapSpecifier(
            name="checkbox22", channel=Channel.from_string("latest/stable")
        )

        mock_install = mocker.patch.object(device.interfaces[SnapInterface], "install")

        frontends = [
            SnapSpecifier(name="checkbox", channel=Channel.from_string("22/stable"))
        ]
        installer = CheckboxSnapsInstaller(
            device, TrivialDevice(), frontends, mocker.Mock()
        )

        strict = installer.install_frontend_snap(frontends[0])

        assert strict is True
        assert device.run.call_count == 2  # download and ack
        mock_install.assert_called_once()

    def test_install_frontend_snap_falls_back_to_classic(self, mocker):
        """Test installing frontend snap falls back to classic on devmode failure."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                RebootInterface(),
                SystemStatusInterface(),
                SnapInterface(),
            ]
        )
        device.run = mocker.Mock(return_value=Result(stdout="", exited=0))

        mocker.patch.object(
            device.interfaces[SnapdAPIClient],
            "get",
            side_effect=[
                {"architecture": "amd64", "store": None},
                [{"store": "branded"}],
            ],
        )
        mocker.patch(
            "toolbox.checkbox.installers.snaps.CheckboxRuntimeHelper"
        ).return_value.determine_checkbox_runtime.return_value = SnapSpecifier(
            name="checkbox22", channel=Channel.from_string("latest/stable")
        )

        # First install fails, second succeeds
        mock_install = mocker.patch.object(
            device.interfaces[SnapInterface],
            "install",
            side_effect=[SnapInstallError("devmode failed"), None],
        )

        frontends = [
            SnapSpecifier(name="checkbox", channel=Channel.from_string("22/stable"))
        ]
        installer = CheckboxSnapsInstaller(
            device, TrivialDevice(), frontends, mocker.Mock()
        )

        strict = installer.install_frontend_snap(frontends[0])

        assert strict is False
        assert mock_install.call_count == 2

    def test_install_frontend_snap_with_store_auth(self, mocker):
        """Test installing frontend snap includes store auth token."""
        mocker.patch.dict(os.environ, {"UBUNTU_STORE_AUTH": "secret-token"})

        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                RebootInterface(),
                SystemStatusInterface(),
                SnapInterface(),
            ]
        )
        device.run = mocker.Mock(return_value=Result(stdout="", exited=0))

        mocker.patch.object(
            device.interfaces[SnapdAPIClient],
            "get",
            side_effect=[
                {"architecture": "amd64", "store": None},
                [{"store": "branded"}],
            ],
        )
        mocker.patch(
            "toolbox.checkbox.installers.snaps.CheckboxRuntimeHelper"
        ).return_value.determine_checkbox_runtime.return_value = SnapSpecifier(
            name="checkbox22", channel=Channel.from_string("latest/stable")
        )
        mocker.patch.object(device.interfaces[SnapInterface], "install")

        frontends = [
            SnapSpecifier(name="checkbox", channel=Channel.from_string("22/stable"))
        ]
        installer = CheckboxSnapsInstaller(
            device, TrivialDevice(), frontends, mocker.Mock()
        )

        installer.install_frontend_snap(frontends[0])

        # Check that download was called with env containing auth token
        download_call = device.run.call_args_list[0]
        assert download_call[1]["env"]["UBUNTU_STORE_AUTH"] == "secret-token"
        assert download_call[1]["env"]["UBUNTU_STORE_ID"] == "branded"

    def test_install_runtime(self, mocker):
        """Test installing runtime snap."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                RebootInterface(),
                SystemStatusInterface(),
                SnapInterface(),
            ]
        )

        mocker.patch.object(
            device.interfaces[SnapdAPIClient],
            "get",
            side_effect=[
                {"architecture": "amd64", "store": None},
                [{"store": "branded"}],
            ],
        )

        runtime = SnapSpecifier(
            name="checkbox22", channel=Channel.from_string("latest/stable")
        )
        mocker.patch(
            "toolbox.checkbox.installers.snaps.CheckboxRuntimeHelper"
        ).return_value.determine_checkbox_runtime.return_value = runtime

        mock_install = mocker.patch.object(device.interfaces[SnapInterface], "install")

        frontends = [
            SnapSpecifier(name="checkbox", channel=Channel.from_string("22/stable"))
        ]
        installer = CheckboxSnapsInstaller(
            device, TrivialDevice(), frontends, mocker.Mock()
        )

        installer.install_runtime()

        mock_install.assert_called_once_with(
            "checkbox22", Channel.from_string("latest/stable"), policy=mocker.ANY
        )

    @pytest.mark.parametrize(
        "frontends,expected_disable_calls",
        [
            # Single frontend - no secondary to disable
            (
                [
                    SnapSpecifier(
                        name="checkbox", channel=Channel.from_string("22/stable")
                    )
                ],
                0,
            ),
            # Two frontends - one secondary to disable
            (
                [
                    SnapSpecifier(
                        name="checkbox", channel=Channel.from_string("22/stable")
                    ),
                    SnapSpecifier(
                        name="checkbox-iiotg", channel=Channel.from_string("22/stable")
                    ),
                ],
                1,
            ),
            # Three frontends - two secondaries to disable
            (
                [
                    SnapSpecifier(
                        name="checkbox", channel=Channel.from_string("22/stable")
                    ),
                    SnapSpecifier(
                        name="checkbox-iiotg", channel=Channel.from_string("22/stable")
                    ),
                    SnapSpecifier(
                        name="checkbox-ce", channel=Channel.from_string("22/stable")
                    ),
                ],
                2,
            ),
        ],
    )
    def test_install_frontends(self, mocker, frontends, expected_disable_calls):
        """Test installing frontends with various numbers of secondary frontends."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                RebootInterface(),
                SystemStatusInterface(),
                SnapInterface(),
            ]
        )
        device.run = mocker.Mock(return_value=Result(stdout="", exited=0))

        mocker.patch.object(
            device.interfaces[SnapdAPIClient],
            "get",
            side_effect=[
                {"architecture": "amd64", "store": None},
                [{"store": "branded"}],
            ],
        )
        mocker.patch(
            "toolbox.checkbox.installers.snaps.CheckboxRuntimeHelper"
        ).return_value.determine_checkbox_runtime.return_value = SnapSpecifier(
            name="checkbox22", channel=Channel.from_string("latest/stable")
        )
        mocker.patch.object(device.interfaces[SnapInterface], "install")

        installer = CheckboxSnapsInstaller(
            device, TrivialDevice(), frontends, mocker.Mock()
        )

        installer.install_frontends()

        # Count disable calls
        disable_calls = [
            call
            for call in device.run.call_args_list
            if call[0][0][1:3] == ["snap", "stop"]
        ]
        assert len(disable_calls) == expected_disable_calls

        # Should always set agent and slave for primary frontend
        calls = [call[0][0] for call in device.run.call_args_list]
        assert ["sudo", "snap", "set", frontends[0].name, "agent=enabled"] in calls
        assert ["sudo", "snap", "set", frontends[0].name, "slave=enabled"] in calls

    def test_perform_connections(self, mocker):
        """Test performing snap connections."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                RebootInterface(),
                SystemStatusInterface(),
                SnapInterface(),
            ]
        )
        device.run = mocker.Mock(return_value=Result(stdout="", exited=0))

        mocker.patch.object(
            device.interfaces[SnapdAPIClient],
            "get",
            side_effect=[
                {"architecture": "amd64", "store": None},
                [{"store": "branded"}],
                {"plugs": [], "slots": []},  # connections data
            ],
        )
        mocker.patch(
            "toolbox.checkbox.installers.snaps.CheckboxRuntimeHelper"
        ).return_value.determine_checkbox_runtime.return_value = SnapSpecifier(
            name="checkbox22", channel=Channel.from_string("latest/stable")
        )

        # Create mock connections that will be returned by the connector
        mock_connection1 = SnapConnection("checkbox", "network", "core", "network")
        mock_connection2 = SnapConnection(
            "checkbox", "hardware-observe", "core", "hardware-observe"
        )

        mock_connector = mocker.Mock()
        mock_connector.process.return_value = (
            [mock_connection1, mock_connection2],
            ["message (for logging)"],
        )
        mocker.patch(
            "toolbox.checkbox.installers.snaps.SnapConnector",
            return_value=mock_connector,
        )

        frontends = [
            SnapSpecifier(name="checkbox", channel=Channel.from_string("22/stable"))
        ]
        installer = CheckboxSnapsInstaller(
            device, TrivialDevice(), frontends, mocker.Mock()
        )

        installer.perform_connections()

        mock_connector.process.assert_called_once()

        # Verify that snap connect was called for each connection
        connect_calls = [
            call
            for call in device.run.call_args_list
            if "snap" in call[0][0] and "connect" in call[0][0]
        ]
        assert len(connect_calls) == 2

    def test_restart(self, mocker):
        """Test restarting frontend snap."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                RebootInterface(),
                SystemStatusInterface(),
                SnapInterface(),
            ]
        )
        device.run = mocker.Mock(return_value=Result(stdout="", exited=0))

        mocker.patch.object(
            device.interfaces[SnapdAPIClient],
            "get",
            side_effect=[
                {"architecture": "amd64", "store": None},
                [{"store": "branded"}],
            ],
        )

        runtime = SnapSpecifier(
            name="checkbox22", channel=Channel.from_string("latest/stable")
        )
        mocker.patch(
            "toolbox.checkbox.installers.snaps.CheckboxRuntimeHelper"
        ).return_value.determine_checkbox_runtime.return_value = runtime

        mock_install = mocker.patch.object(device.interfaces[SnapInterface], "install")

        frontends = [
            SnapSpecifier(name="checkbox", channel=Channel.from_string("22/stable"))
        ]
        installer = CheckboxSnapsInstaller(
            device, TrivialDevice(), frontends, mocker.Mock()
        )

        installer.restart()

        # Should refresh runtime and restart frontend
        mock_install.assert_called_once_with(
            "checkbox22", Channel.from_string("latest/stable"), policy=mocker.ANY
        )
        device.run.assert_called_once_with(["sudo", "snap", "restart", "checkbox"])

    def test_install_on_device(self, mocker):
        """Test install_on_device orchestrates all installation steps."""
        device = TrivialDevice(
            interfaces=[
                SnapdAPIClient(),
                RebootInterface(),
                SystemStatusInterface(),
                SnapInterface(),
            ]
        )

        mocker.patch.object(
            device.interfaces[SnapdAPIClient],
            "get",
            side_effect=[
                {"architecture": "amd64", "store": None},
                [{"store": "branded"}],
            ],
        )
        mocker.patch(
            "toolbox.checkbox.installers.snaps.CheckboxRuntimeHelper"
        ).return_value.determine_checkbox_runtime.return_value = SnapSpecifier(
            name="checkbox22", channel=Channel.from_string("latest/stable")
        )

        frontends = [
            SnapSpecifier(name="checkbox", channel=Channel.from_string("22/stable"))
        ]
        installer = CheckboxSnapsInstaller(
            device, TrivialDevice(), frontends, mocker.Mock()
        )

        mock_install_runtime = mocker.patch.object(installer, "install_runtime")
        mock_install_frontends = mocker.patch.object(installer, "install_frontends")
        mock_perform_connections = mocker.patch.object(installer, "perform_connections")
        mock_restart = mocker.patch.object(installer, "restart")

        installer.install_on_device()

        mock_install_runtime.assert_called_once()
        mock_install_frontends.assert_called_once()
        mock_perform_connections.assert_called_once()
        mock_restart.assert_called_once()
