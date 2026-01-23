"""Tests for SnapConnection entity."""

import pytest

from toolbox.entities.connections import SnapConnection


class TestSnapConnectionInitialization:
    """Tests for SnapConnection initialization."""

    def test_snap_connection_basic(self):
        """Test creating a basic snap connection."""
        connection = SnapConnection(
            plug_snap="checkbox",
            plug_name="network",
            slot_snap="snapd",
            slot_name="network",
        )
        assert connection.plug_snap == "checkbox"
        assert connection.plug_name == "network"
        assert connection.slot_snap == "snapd"
        assert connection.slot_name == "network"

    def test_snap_connection_content_interface(self):
        """Test creating a content interface connection."""
        connection = SnapConnection(
            plug_snap="checkbox-mir",
            plug_name="graphics-core22",
            slot_snap="mesa-core22",
            slot_name="graphics-core22",
        )
        assert connection.plug_snap == "checkbox-mir"
        assert connection.plug_name == "graphics-core22"
        assert connection.slot_snap == "mesa-core22"
        assert connection.slot_name == "graphics-core22"


class TestSnapConnectionFromDicts:
    """Tests for SnapConnection.from_dicts() method."""

    def test_from_dicts_basic(self):
        """Test creating a connection from plug and slot dicts."""
        plug = {
            "snap": "checkbox",
            "plug": "network",
            "interface": "network",
        }
        slot = {
            "snap": "snapd",
            "slot": "network",
            "interface": "network",
        }
        connection = SnapConnection.from_dicts(plug, slot)
        assert connection.plug_snap == "checkbox"
        assert connection.plug_name == "network"
        assert connection.slot_snap == "snapd"
        assert connection.slot_name == "network"

    def test_from_dicts_content_interface(self):
        """Test creating a content interface connection from dicts."""
        plug = {
            "snap": "checkbox-mir",
            "plug": "graphics-core22",
            "interface": "content",
            "attrs": {
                "content": "graphics-core22",
                "default-provider": "mesa-core22",
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
        connection = SnapConnection.from_dicts(plug, slot)
        assert connection.plug_snap == "checkbox-mir"
        assert connection.plug_name == "graphics-core22"
        assert connection.slot_snap == "mesa-core22"
        assert connection.slot_name == "graphics-core22"


class TestSnapConnectionFromString:
    """Tests for SnapConnection.from_string() method."""

    @pytest.mark.parametrize(
        "connection_string,expected_plug_snap,expected_plug_name,expected_slot_snap,expected_slot_name",
        [
            # explicit slot snap
            (
                "checkbox:network/snapd:network",
                "checkbox",
                "network",
                "snapd",
                "network",
            ),
            (
                "checkbox-mir:graphics-core22/mesa-core22:graphics-core22",
                "checkbox-mir",
                "graphics-core22",
                "mesa-core22",
                "graphics-core22",
            ),
            ("my-snap:home/core:home", "my-snap", "home", "core", "home"),
            # implicit snapd slot snap (empty string before colon)
            ("checkbox:network/:network", "checkbox", "network", "snapd", "network"),
            (
                "test-snap:audio-playback/:audio-playback",
                "test-snap",
                "audio-playback",
                "snapd",
                "audio-playback",
            ),
        ],
    )
    def test_snap_connection_from_string_valid(
        self,
        connection_string,
        expected_plug_snap,
        expected_plug_name,
        expected_slot_snap,
        expected_slot_name,
    ):
        """Test parsing valid snap connection strings."""
        connection = SnapConnection.from_string(connection_string)
        assert connection.plug_snap == expected_plug_snap
        assert connection.plug_name == expected_plug_name
        assert connection.slot_snap == expected_slot_snap
        assert connection.slot_name == expected_slot_name

    @pytest.mark.parametrize(
        "invalid_string",
        [
            "checkbox:network",
            "checkbox/snapd:network",
            ":network/:network",
            "checkbox:/:network",
            "",
            "invalid",
        ],
    )
    def test_snap_connection_from_string_invalid(self, invalid_string):
        """Test that parsing invalid connection strings raises ValueError."""
        with pytest.raises(
            ValueError, match="cannot be converted to a snap connection"
        ):
            SnapConnection.from_string(invalid_string)


class TestSnapConnectionStringRepresentation:
    """Tests for SnapConnection.__str__() method."""

    @pytest.mark.parametrize(
        "plug_snap,plug_name,slot_snap,slot_name,expected_string",
        [
            (
                "checkbox",
                "network",
                "snapd",
                "network",
                "checkbox:network/snapd:network",
            ),
            (
                "checkbox-mir",
                "graphics-core22",
                "mesa-core22",
                "graphics-core22",
                "checkbox-mir:graphics-core22/mesa-core22:graphics-core22",
            ),
            ("my-snap", "home", "core", "home", "my-snap:home/core:home"),
            ("test", "audio", "snapd", "audio", "test:audio/snapd:audio"),
        ],
    )
    def test_snap_connection_str(
        self, plug_snap, plug_name, slot_snap, slot_name, expected_string
    ):
        """Test string representation of snap connections."""
        connection = SnapConnection(
            plug_snap=plug_snap,
            plug_name=plug_name,
            slot_snap=slot_snap,
            slot_name=slot_name,
        )
        assert str(connection) == expected_string
