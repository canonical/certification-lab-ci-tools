import json
import pytest
from io import StringIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from textwrap import dedent
from unittest.mock import patch

# Import the module
from toolbox import snap_connections
from toolbox.snap_connections import Connection, Connector, Blacklist


class TestConnection:
    def test_from_dicts(self):
        plug = {
            "snap": "checkbox-mir",
            "plug": "graphics-core22",
            "interface": "content",
            "attrs": {
                "content": "graphics-core22",
            },
        }
        slot = {
            "snap": "mesa-core22",
            "slot": "graphics-core22",
            "interface": "content",
            "attrs": {
                "content": "graphics-core22",
            },
        }

        connection = Connection.from_dicts(plug, slot)
        assert connection == Connection(
            "checkbox-mir", "graphics-core22", "mesa-core22", "graphics-core22"
        )

    def test_from_string(self):
        connection = Connection.from_string(
            "checkbox:checkbox-runtime/checkbox24:checkbox-runtime"
        )
        assert connection == Connection(
            "checkbox", "checkbox-runtime", "checkbox24", "checkbox-runtime"
        )

    def test_from_string_empty_slot_snap(self):
        connection = Connection.from_string("console-conf:snapd-control/:snapd-control")
        assert connection == Connection(
            "console-conf", "snapd-control", "snapd", "snapd-control"
        )

    def test_from_string_invalid(self):
        with pytest.raises(ValueError):
            Connection.from_string("invalid-format")

        with pytest.raises(ValueError):
            Connection.from_string("snap1/snap2")

        with pytest.raises(ValueError):
            Connection.from_string("snap1:plug1:snap2:slot1")

    def test_string_representation(self):
        connection = Connection(
            plug_snap="checkbox",
            plug_name="checkbox-runtime",
            slot_snap="checkbox24",
            slot_name="checkbox-runtime",
        )
        assert (
            str(connection) == "checkbox:checkbox-runtime/checkbox24:checkbox-runtime"
        )


class TestConnector:
    def test_matching_attributes_no_attrs(self):
        plug = {"interface": "test"}
        slot = {"interface": "test"}
        assert Connector.matching_attributes(plug, slot)

    def test_matching_attributes_no_common_attrs(self):
        plug = {"interface": "content", "attrs": {"attr1": "value1"}}
        slot = {"interface": "content", "attrs": {"attr2": "value2"}}
        assert Connector.matching_attributes(plug, slot)

    def test_matching_attributes_matching_attrs(self):
        plug = {
            "interface": "content",
            "attrs": {"content": "graphics-core22", "extra": "value"},
        }
        slot = {
            "interface": "content",
            "attrs": {"content": "graphics-core22", "other": "data"},
        }
        assert Connector.matching_attributes(plug, slot)

    def test_matching_attributes_non_matching_attrs(self):
        plug = {"interface": "content", "attrs": {"content": "graphics-core22"}}
        slot = {"interface": "content", "attrs": {"content": "different-value"}}
        assert not Connector.matching_attributes(plug, slot)

    def test_init_default_predicates(self):
        connector = Connector()
        assert len(connector.predicates) == 2

    def test_process_with_existing_connections(self):
        data = {
            "result": {
                "plugs": [
                    {
                        "snap": "connected-plug-snap",
                        "plug": "plug",
                        "interface": "interface",
                        "connections": [
                            {"snap": "connected-slot-snap", "slot": "slot"}
                        ],
                    },
                    {
                        "snap": "disconnected-plug-snap",
                        "plug": "plug",
                        "interface": "interface",
                    },
                ],
                "slots": [
                    {
                        "snap": "slot-snap",
                        "slot": "slot",
                        "interface": "interface",
                        "connections": [
                            {"snap": "connected-plug-snap", "plug": "plug"}
                        ],
                    }
                ],
            }
        }

        connector = Connector()
        connections = sorted(connector.process(data))

        assert len(connections) == 1
        assert str(connections[0]) == "disconnected-plug-snap:plug/slot-snap:slot"

    def test_process_same_snap_rejection(self):
        data = {
            "result": {
                "plugs": [{"snap": "snap", "plug": "plug", "interface": "interface"}],
                "slots": [
                    {
                        "snap": "snap",  # Same snap as the plug
                        "slot": "slot",
                        "interface": "interface",
                    }
                ],
            }
        }

        connector = Connector()
        connections = connector.process(data)

        # Should reject connections on the same snap
        assert len(connections) == 0

    def test_process_with_custom_predicate(self):
        data = {
            "result": {
                "plugs": [
                    {"snap": "allowed-snap", "plug": "plug", "interface": "interface"},
                    {"snap": "rejected-snap", "plug": "plug", "interface": "interface"},
                ],
                "slots": [
                    {"snap": "slot-snap", "slot": "slot", "interface": "interface"}
                ],
            }
        }

        # Only allow connections from "allowed-snap"
        def predicate(plug, slot):
            return plug["snap"] == "allowed-snap"

        connector = Connector(predicates=[predicate])
        connections = connector.process(data)

        # Should only find one connection from allowed-snap
        assert len(connections) == 1
        connection = list(connections)[0]
        assert connection.plug_snap == "allowed-snap"

    def test_process_multiple_slots_per_plug(self):
        data = {
            "result": {
                "plugs": [
                    {"snap": "checkbox", "plug": "gpio", "interface": "gpio"},
                ],
                "slots": [
                    {
                        "snap": "pi",
                        "slot": "bcm-gpio-1",
                        "interface": "gpio",
                        "attrs": {"number": 1},
                    },
                    {
                        "snap": "pi",
                        "slot": "bcm-gpio-10",
                        "interface": "gpio",
                        "attrs": {"number": 10},
                    },
                ],
            }
        }

        connector = Connector()
        connections = connector.process(data)

        # plug should be connected to both slots
        assert len(connections) == 2

    def test_process_with_non_matching_attributes(self):
        data = {
            "result": {
                "plugs": [
                    {
                        "snap": "plug-snap",
                        "plug": "plug",
                        "interface": "content",
                        "attrs": {"content": "value"},
                    }
                ],
                "slots": [
                    {
                        "snap": "slot-snap",
                        "slot": "slot",
                        "interface": "content",
                        "attrs": {"content": "different-value"},
                    }
                ],
            }
        }

        connector = Connector()
        connections = connector.process(data)

        # Should reject due to non-matching attributes
        assert len(connections) == 0


class TestBlacklist:
    @pytest.mark.parametrize(
        "blacklist_data,expected_connections",
        [
            # single item, single match
            (
                {
                    "items": [
                        {
                            "match": [
                                {
                                    "plug_snap": "firefox",
                                    "plug_name": "camera",
                                    "slot_snap": "snapd",
                                    "slot_name": "camera",
                                }
                            ]
                        }
                    ]
                },
                [Connection("firefox", "camera", "snapd", "camera")],
            ),
            # mutiple items, multiple matches
            (
                {
                    "items": [
                        {
                            "match": [
                                {
                                    "plug_snap": "chromium",
                                    "plug_name": "home",
                                    "slot_snap": "snapd",
                                    "slot_name": "home",
                                },
                                {
                                    "plug_snap": "vlc",
                                    "plug_name": "audio-playback",
                                    "slot_snap": "pulseaudio",
                                    "slot_name": "audio-playback",
                                },
                            ]
                        },
                        {
                            "match": [
                                {
                                    "plug_snap": "code",
                                    "plug_name": "desktop",
                                    "slot_snap": "gtk-common-themes",
                                    "slot_name": "gtk-3-themes",
                                }
                            ]
                        },
                    ]
                },
                [
                    Connection("chromium", "home", "snapd", "home"),
                    Connection("vlc", "audio-playback", "pulseaudio", "audio-playback"),
                    Connection("code", "desktop", "gtk-common-themes", "gtk-3-themes"),
                ],
            ),
            # None entries, i.e. wildcards
            (
                {
                    "items": [
                        {
                            "match": [
                                {
                                    "plug_snap": None,
                                    "plug_name": "network",
                                    "slot_snap": "snapd",
                                    "slot_name": None,
                                }
                            ]
                        }
                    ]
                },
                [Connection(None, "network", "snapd", None)],
            ),
        ],
    )
    def test_extract_connections(self, blacklist_data, expected_connections):
        connections = Blacklist.extract_connections(blacklist_data)
        assert connections == expected_connections

    @pytest.mark.parametrize(
        "connections,plug,slot,expected_allowed",
        [
            # Exact match - should be blacklisted
            (
                [Connection("firefox", "camera", "snapd", "camera")],
                {"snap": "firefox", "plug": "camera"},
                {"snap": "snapd", "slot": "camera"},
                False,
            ),
            # No match - should be allowed
            (
                [Connection("firefox", "camera", "snapd", "camera")],
                {"snap": "chromium", "plug": "camera"},
                {"snap": "snapd", "slot": "camera"},
                True,
            ),
            # Wildcard plug_snap - should be blacklisted
            (
                [Connection(None, "network", "snapd", "network")],
                {"snap": "firefox", "plug": "network"},
                {"snap": "snapd", "slot": "network"},
                False,
            ),
            # Wildcard plug_snap - different snap should still be blacklisted
            (
                [Connection(None, "network", "snapd", "network")],
                {"snap": "chromium", "plug": "network"},
                {"snap": "snapd", "slot": "network"},
                False,
            ),
            # Wildcard plug_name - should be blacklisted
            (
                [Connection("vlc", None, "pulseaudio", "audio-playback")],
                {"snap": "vlc", "plug": "audio-record"},
                {"snap": "pulseaudio", "slot": "audio-playback"},
                False,
            ),
            # Wildcard plug_name - different plug name should still be blacklisted
            (
                [Connection("vlc", None, "pulseaudio", "audio-playback")],
                {"snap": "vlc", "plug": "desktop"},
                {"snap": "pulseaudio", "slot": "audio-playback"},
                False,
            ),
            # Wildcard slot_snap - should be blacklisted
            (
                [Connection("code", "desktop", None, "gtk-3-themes")],
                {"snap": "code", "plug": "desktop"},
                {"snap": "gtk-common-themes", "slot": "gtk-3-themes"},
                False,
            ),
            # Wildcard slot_snap - different slot snap should still be blacklisted
            (
                [Connection("code", "desktop", None, "gtk-3-themes")],
                {"snap": "code", "plug": "desktop"},
                {"snap": "gtk3-themes", "slot": "gtk-3-themes"},
                False,
            ),
            # Wildcard slot_name - should be blacklisted
            (
                [Connection("gimp", "home", "snapd", None)],
                {"snap": "gimp", "plug": "home"},
                {"snap": "snapd", "slot": "home"},
                False,
            ),
            # Wildcard slot_name - different slot name should still be blacklisted
            (
                [Connection("gimp", "home", "snapd", None)],
                {"snap": "gimp", "plug": "home"},
                {"snap": "snapd", "slot": "removable-media"},
                False,
            ),
            # Multiple entries, one matches - should be blacklisted
            (
                [
                    Connection("discord", "audio-record", "pulseaudio", "audio-record"),
                    Connection("slack", "camera", "snapd", "camera"),
                    Connection("firefox", "network", "snapd", "network"),
                ],
                {"snap": "firefox", "plug": "network"},
                {"snap": "snapd", "slot": "network"},
                False,
            ),
            # Multiple entries, none match - should be allowed
            (
                [
                    Connection("discord", "audio-record", "pulseaudio", "audio-record"),
                    Connection("slack", "camera", "snapd", "camera"),
                    Connection(
                        "spotify", "audio-playback", "pulseaudio", "audio-playback"
                    ),
                ],
                {"snap": "firefox", "plug": "network"},
                {"snap": "snapd", "slot": "network"},
                True,
            ),
            # Wildcard plug_snap and plug_name - should be blacklisted
            (
                [Connection(None, None, "snapd", "network")],
                {"snap": "firefox", "plug": "network-bind"},
                {"snap": "snapd", "slot": "network"},
                False,
            ),
            # Wildcard slot_snap and slot_name - should be blacklisted
            (
                [Connection("telegram-desktop", "audio-playback", None, None)],
                {"snap": "telegram-desktop", "plug": "audio-playback"},
                {"snap": "pulseaudio", "slot": "audio-playback"},
                False,
            ),
            # All wildcards - should blacklist everything
            (
                [Connection(None, None, None, None)],
                {"snap": "thunderbird", "plug": "home"},
                {"snap": "snapd", "slot": "home"},
                False,
            ),
        ],
    )
    def test_is_allowed(self, connections, plug, slot, expected_allowed):
        blacklist = Blacklist(connections)
        assert blacklist.is_allowed(plug, slot) == expected_allowed


class TestMainFunction:
    def test_main_no_args(self):
        with pytest.raises(SystemExit):
            snap_connections.main([])

    @patch("sys.stdin")
    @patch("sys.stdout", new_callable=StringIO)
    def test_main_with_snaps_predicate(self, mock_stdout, mock_stdin):
        # Prepare mock input data
        mock_data = {
            "result": {
                "plugs": [
                    {
                        "snap": "allowed-plug-snap-1",
                        "plug": "plug-name",
                        "interface": "interface",
                    },
                    {
                        "snap": "filtered-out-plug-snap",
                        "plug": "plug-name",
                        "interface": "interface",
                    },
                    {
                        "snap": "allowed-plug-snap-2",
                        "plug": "plug-name",
                        "interface": "interface",
                    },
                ],
                "slots": [
                    {"snap": "slot-snap", "slot": "slot-name", "interface": "interface"}
                ],
            }
        }
        mock_stdin.read.return_value = json.dumps(mock_data)

        test_args = ["allowed-plug-snap-1", "allowed-plug-snap-2"]
        snap_connections.main(test_args)

        # Check the output - should only include connections from allowed-snap
        output = mock_stdout.getvalue().strip()
        assert "allowed-plug-snap-1:plug-name/slot-snap:slot-name" in output
        assert "allowed-plug-snap-2:plug-name/slot-snap:slot-name" in output
        assert "filtered-out-plug-snap" not in output

    @patch("sys.stdin")
    @patch("sys.stdout", new_callable=StringIO)
    def test_main_with_force_option(self, mock_stdout, mock_stdin):
        # Prepare mock input data with no possible connections
        mock_data = {"result": {"plugs": [], "slots": []}}
        mock_stdin.read.return_value = json.dumps(mock_data)

        # forced connection doesn't need to pertain to the specified snaps
        test_args = ["other-snap", "--force", "plug-snap:plug/slot-snap:slot"]
        snap_connections.main(test_args)

        # Check the output - should include the forced connection
        output = mock_stdout.getvalue().strip()
        assert output == "plug-snap:plug/slot-snap:slot"

    @patch("sys.stdin")
    @patch("sys.stdout", new_callable=StringIO)
    def test_main_with_blacklist_option(self, mock_stdout, mock_stdin):
        # Prepare mock input data
        mock_data = {
            "result": {
                "plugs": [
                    {
                        "snap": "allowed-snap",
                        "plug": "allowed-plug",
                        "interface": "interface",
                    },
                    {
                        "snap": "blacklisted-snap",
                        "plug": "blacklisted-plug",
                        "interface": "interface",
                    },
                ],
                "slots": [
                    {"snap": "slot-snap", "slot": "slot-name", "interface": "interface"}
                ],
            }
        }
        mock_stdin.read.return_value = json.dumps(mock_data)

        # Create temporary blacklist file
        blacklist_content = dedent("""
            items:
              - match:
                - plug_snap: blacklisted-snap
                  plug_name: blacklisted-plug
                  slot_snap: slot-snap
                  slot_name: slot-name
            """)
        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as temp_file:
            temp_file.write(blacklist_content)
            temp_file_path = Path(temp_file.name)

        try:
            test_args = [
                "allowed-snap",
                "blacklisted-snap",
                "--blacklist",
                str(temp_file_path),
            ]
            snap_connections.main(test_args)

            # Check the output - should only include allowed connections
            output = mock_stdout.getvalue().strip()
            assert "allowed-snap:allowed-plug/slot-snap:slot-name" in output
            assert "blacklisted-snap:blacklisted-plug/slot-snap:slot-name" not in output
        finally:
            temp_file_path.unlink()

    @patch("sys.stdin")
    @patch("sys.stdout", new_callable=StringIO)
    def test_main_with_blacklist_wildcard_patterns(self, mock_stdout, mock_stdin):
        # Prepare mock input data
        mock_data = {
            "result": {
                "plugs": [
                    {
                        "snap": "test-snap",
                        "plug": "allowed-plug",
                        "interface": "interface",
                    },
                    {
                        "snap": "test-snap",
                        "plug": "blocked-plug",
                        "interface": "interface",
                    },
                ],
                "slots": [
                    {"snap": "slot-snap", "slot": "slot-name", "interface": "interface"}
                ],
            }
        }
        mock_stdin.read.return_value = json.dumps(mock_data)

        # Create blacklist that blocks any connection with "blocked-plug" name
        blacklist_content = dedent("""
            items:
              - match:
                - plug_snap: null
                  plug_name: blocked-plug
                  slot_snap: null
                  slot_name: null
            """)
        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as temp_file:
            temp_file.write(blacklist_content)
            temp_file_path = Path(temp_file.name)

        try:
            test_args = ["test-snap", "--blacklist", str(temp_file_path)]
            snap_connections.main(test_args)

            # Check the output - should exclude blocked-plug connections
            output = mock_stdout.getvalue().strip()
            assert "test-snap:allowed-plug/slot-snap:slot-name" in output
            assert "blocked-plug" not in output
        finally:
            temp_file_path.unlink()
