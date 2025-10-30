"""Tests for snap connection connector and predicates."""

import pytest
from pathlib import Path
from textwrap import dedent

from toolbox.checkbox.helpers.connector import (
    Blacklist,
    DifferentSnaps,
    MatchAttributes,
    SelectSnaps,
    SnapConnector,
)
from toolbox.entities.connections import SnapConnection


class TestMatchAttributesPredicate:
    """Tests for MatchAttributes predicate."""

    def test_matching_attributes_no_attrs(self):
        """Test that connections without attrs are allowed."""
        plug = {"interface": "test"}
        slot = {"interface": "test"}
        assert MatchAttributes.check(plug, slot)

    def test_matching_attributes_no_common_attrs(self):
        """Test that connections with no common attrs are allowed."""
        plug = {"interface": "content", "attrs": {"attr1": "value1"}}
        slot = {"interface": "content", "attrs": {"attr2": "value2"}}
        assert MatchAttributes.check(plug, slot)

    def test_matching_attributes_matching_attrs(self):
        """Test that connections with matching common attrs are allowed."""
        plug = {
            "interface": "content",
            "attrs": {"content": "graphics-core22", "extra": "value"},
        }
        slot = {
            "interface": "content",
            "attrs": {"content": "graphics-core22", "other": "data"},
        }
        assert MatchAttributes.check(plug, slot)

    def test_matching_attributes_non_matching_attrs(self):
        """Test that connections with non-matching common attrs are rejected."""
        plug = {"interface": "content", "attrs": {"content": "graphics-core22"}}
        slot = {"interface": "content", "attrs": {"content": "different-value"}}
        assert not MatchAttributes.check(plug, slot)


class TestDifferentSnapsPredicate:
    """Tests for DifferentSnaps predicate."""

    def test_different_snaps_allowed(self):
        """Test that connections between different snaps are allowed."""
        plug = {"snap": "checkbox", "plug": "network"}
        slot = {"snap": "snapd", "slot": "network"}
        assert DifferentSnaps.check(plug, slot)

    def test_same_snap_rejected(self):
        """Test that connections within the same snap are rejected."""
        plug = {"snap": "mysnap", "plug": "plug"}
        slot = {"snap": "mysnap", "slot": "slot"}
        assert not DifferentSnaps.check(plug, slot)


class TestSelectSnapsPredicate:
    """Tests for SelectSnaps predicate."""

    def test_select_single_snap(self):
        """Test selecting connections from a single snap."""
        predicate = SelectSnaps(["checkbox"])
        plug = {"snap": "checkbox", "plug": "network"}
        slot = {"snap": "snapd", "slot": "network"}
        assert predicate.check(plug, slot)

    def test_select_multiple_snaps(self):
        """Test selecting connections from multiple snaps."""
        predicate = SelectSnaps(["checkbox", "firefox"])

        plug1 = {"snap": "checkbox", "plug": "network"}
        slot = {"snap": "snapd", "slot": "network"}
        assert predicate.check(plug1, slot)

        plug2 = {"snap": "firefox", "plug": "network"}
        assert predicate.check(plug2, slot)

    def test_reject_non_selected_snap(self):
        """Test that connections from non-selected snaps are rejected."""
        predicate = SelectSnaps(["checkbox"])
        plug = {"snap": "firefox", "plug": "network"}
        slot = {"snap": "snapd", "slot": "network"}
        assert not predicate.check(plug, slot)


class TestBlacklistPredicate:
    """Tests for Blacklist predicate."""

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
                [SnapConnection("firefox", "camera", "snapd", "camera")],
            ),
            # multiple items, multiple matches
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
                    SnapConnection("chromium", "home", "snapd", "home"),
                    SnapConnection(
                        "vlc", "audio-playback", "pulseaudio", "audio-playback"
                    ),
                    SnapConnection(
                        "code", "desktop", "gtk-common-themes", "gtk-3-themes"
                    ),
                ],
            ),
            # None entries (wildcards)
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
                [SnapConnection(None, "network", "snapd", None)],
            ),
        ],
    )
    def test_blacklist_from_dict(self, blacklist_data, expected_connections):
        """Test creating blacklist from dict with various configurations."""
        connections = Blacklist.from_dict(blacklist_data).blacklist
        assert connections == expected_connections

    @pytest.mark.parametrize(
        "connections,plug,slot,expected_allowed",
        [
            # exact match - should be blacklisted
            (
                [SnapConnection("firefox", "camera", "snapd", "camera")],
                {"snap": "firefox", "plug": "camera"},
                {"snap": "snapd", "slot": "camera"},
                False,
            ),
            # no match - should be allowed
            (
                [SnapConnection("firefox", "camera", "snapd", "camera")],
                {"snap": "chromium", "plug": "camera"},
                {"snap": "snapd", "slot": "camera"},
                True,
            ),
            # wildcard plug_snap
            (
                [SnapConnection(None, "network", "snapd", "network")],
                {"snap": "firefox", "plug": "network"},
                {"snap": "snapd", "slot": "network"},
                False,
            ),
            (
                [SnapConnection(None, "network", "snapd", "network")],
                {"snap": "chromium", "plug": "network"},
                {"snap": "snapd", "slot": "network"},
                False,
            ),
            # wildcard plug_name
            (
                [SnapConnection("vlc", None, "pulseaudio", "audio-playback")],
                {"snap": "vlc", "plug": "audio-record"},
                {"snap": "pulseaudio", "slot": "audio-playback"},
                False,
            ),
            (
                [SnapConnection("vlc", None, "pulseaudio", "audio-playback")],
                {"snap": "vlc", "plug": "desktop"},
                {"snap": "pulseaudio", "slot": "audio-playback"},
                False,
            ),
            # wildcard slot_snap
            (
                [SnapConnection("code", "desktop", None, "gtk-3-themes")],
                {"snap": "code", "plug": "desktop"},
                {"snap": "gtk-common-themes", "slot": "gtk-3-themes"},
                False,
            ),
            (
                [SnapConnection("code", "desktop", None, "gtk-3-themes")],
                {"snap": "code", "plug": "desktop"},
                {"snap": "gtk3-themes", "slot": "gtk-3-themes"},
                False,
            ),
            # wildcard slot_name
            (
                [SnapConnection("gimp", "home", "snapd", None)],
                {"snap": "gimp", "plug": "home"},
                {"snap": "snapd", "slot": "home"},
                False,
            ),
            (
                [SnapConnection("gimp", "home", "snapd", None)],
                {"snap": "gimp", "plug": "home"},
                {"snap": "snapd", "slot": "removable-media"},
                False,
            ),
            # multiple entries, one matches
            (
                [
                    SnapConnection(
                        "discord", "audio-record", "pulseaudio", "audio-record"
                    ),
                    SnapConnection("slack", "camera", "snapd", "camera"),
                    SnapConnection("firefox", "network", "snapd", "network"),
                ],
                {"snap": "firefox", "plug": "network"},
                {"snap": "snapd", "slot": "network"},
                False,
            ),
            # multiple entries, none match
            (
                [
                    SnapConnection(
                        "discord", "audio-record", "pulseaudio", "audio-record"
                    ),
                    SnapConnection("slack", "camera", "snapd", "camera"),
                    SnapConnection(
                        "spotify", "audio-playback", "pulseaudio", "audio-playback"
                    ),
                ],
                {"snap": "firefox", "plug": "network"},
                {"snap": "snapd", "slot": "network"},
                True,
            ),
            # all wildcards - blacklist everything
            (
                [SnapConnection(None, None, None, None)],
                {"snap": "thunderbird", "plug": "home"},
                {"snap": "snapd", "slot": "home"},
                False,
            ),
        ],
    )
    def test_blacklist_check(self, connections, plug, slot, expected_allowed):
        """Test blacklist predicate with various wildcard patterns."""
        blacklist = Blacklist(connections)
        result = blacklist.check(plug, slot)
        assert result.result == expected_allowed
        if not expected_allowed:
            assert result.message is not None
            assert "blacklisted" in result.message.lower()

    def test_blacklist_from_file(self, mocker):
        """Test loading blacklist from YAML file."""
        yaml_content = dedent("""
            items:
              - match:
                - plug_snap: firefox
                  plug_name: camera
                  slot_snap: snapd
                  slot_name: camera
        """)

        mocker.patch("builtins.open", mocker.mock_open(read_data=yaml_content))

        blacklist = Blacklist.from_file(Path("fake_blacklist.yaml"))

        plug = {"snap": "firefox", "plug": "camera"}
        slot = {"snap": "snapd", "slot": "camera"}
        assert not blacklist.check(plug, slot)


class TestSnapConnector:
    """Tests for SnapConnector."""

    def test_init_default_predicates(self):
        """Test that connector initializes with default predicates."""
        connector = SnapConnector()
        assert len(connector.predicates) == 2
        assert MatchAttributes in connector.predicates
        assert DifferentSnaps in connector.predicates

    def test_init_with_custom_predicates(self):
        """Test that connector accepts custom predicates."""
        custom_predicate = SelectSnaps(["checkbox"])
        connector = SnapConnector(predicates=[custom_predicate])
        assert len(connector.predicates) == 3
        assert custom_predicate in connector.predicates

    def test_process_with_existing_connections(self):
        """Test that already-connected plugs are not processed."""
        data = {
            "plugs": [
                {
                    "snap": "connected-plug-snap",
                    "plug": "plug",
                    "interface": "interface",
                    "connections": [{"snap": "connected-slot-snap", "slot": "slot"}],
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
                    "connections": [{"snap": "connected-plug-snap", "plug": "plug"}],
                }
            ],
        }

        connector = SnapConnector()
        connections, messages = connector.process(data)

        assert len(connections) == 1
        connection = list(connections)[0]
        assert str(connection) == "disconnected-plug-snap:plug/slot-snap:slot"

    def test_process_same_snap_rejection(self):
        """Test that connections within the same snap are rejected."""
        data = {
            "plugs": [{"snap": "snap", "plug": "plug", "interface": "interface"}],
            "slots": [
                {
                    "snap": "snap",
                    "slot": "slot",
                    "interface": "interface",
                }
            ],
        }

        connector = SnapConnector()
        connections, messages = connector.process(data)

        assert len(connections) == 0

    def test_process_multiple_slots_per_plug(self):
        """Test that a single plug can be connected to multiple slots."""
        data = {
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

        connector = SnapConnector()
        connections, messages = connector.process(data)

        assert len(connections) == 2

    def test_process_with_non_matching_attributes(self):
        """Test that connections with non-matching attributes are rejected."""
        data = {
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

        connector = SnapConnector()
        connections, messages = connector.process(data)

        assert len(connections) == 0

    def test_process_returns_messages(self):
        """Test that connector returns messages from predicates."""
        data = {
            "plugs": [
                {"snap": "allowed-snap", "plug": "plug", "interface": "interface"},
                {"snap": "blacklisted-snap", "plug": "plug", "interface": "interface"},
            ],
            "slots": [{"snap": "slot-snap", "slot": "slot", "interface": "interface"}],
        }

        blacklist = Blacklist(
            [SnapConnection("blacklisted-snap", "plug", "slot-snap", "slot")]
        )
        connector = SnapConnector(predicates=[blacklist])
        connections, messages = connector.process(data)

        assert len(connections) == 1
        assert len(messages) == 1
        assert "blacklisted" in messages[0].lower()

    def test_process_with_select_snaps_predicate(self):
        """Test connector with SelectSnaps predicate."""
        data = {
            "plugs": [
                {"snap": "checkbox", "plug": "network", "interface": "network"},
                {"snap": "firefox", "plug": "network", "interface": "network"},
                {"snap": "chrome", "plug": "network", "interface": "network"},
            ],
            "slots": [{"snap": "snapd", "slot": "network", "interface": "network"}],
        }

        select_snaps = SelectSnaps(["checkbox", "firefox"])
        connector = SnapConnector(predicates=[select_snaps])
        connections, messages = connector.process(data)

        assert len(connections) == 2
        plug_snaps = {conn.plug_snap for conn in connections}
        assert plug_snaps == {"checkbox", "firefox"}
