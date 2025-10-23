"""Tests for SnapSpecifier entity."""

import pytest

from toolbox.entities.channels import Channel
from toolbox.entities.snaps import SnapSpecifier


class TestSnapSpecifierInitialization:
    """Tests for SnapSpecifier initialization."""

    def test_snap_specifier_with_track_only(self):
        """Test creating a snap specifier with a track-only channel."""
        channel = Channel(track="latest")
        snap = SnapSpecifier(name="checkbox", channel=channel)
        assert snap.name == "checkbox"
        assert snap.channel == channel

    def test_snap_specifier_with_risk_only(self):
        """Test creating a snap specifier with a risk-only channel."""
        channel = Channel(risk="stable")
        snap = SnapSpecifier(name="checkbox", channel=channel)
        assert snap.name == "checkbox"
        assert snap.channel == channel

    def test_snap_specifier_with_full_channel(self):
        """Test creating a snap specifier with a full channel."""
        channel = Channel(track="22", risk="stable", branch="hotfix")
        snap = SnapSpecifier(name="checkbox", channel=channel)
        assert snap.name == "checkbox"
        assert snap.channel == channel


class TestSnapSpecifierFromString:
    """Tests for SnapSpecifier.from_string() method."""

    @pytest.mark.parametrize(
        "specifier_string,expected_name,expected_channel_str",
        [
            ("checkbox=stable", "checkbox", "stable"),
            ("checkbox=latest/stable", "checkbox", "latest/stable"),
            ("checkbox=22/candidate", "checkbox", "22/candidate"),
            ("checkbox=edge/feature", "checkbox", "edge/feature"),
            ("checkbox=22/stable/hotfix", "checkbox", "22/stable/hotfix"),
            ("my-snap=beta", "my-snap", "beta"),
            ("test-snap=1.0/edge", "test-snap", "1.0/edge"),
        ],
    )
    def test_snap_specifier_from_string_valid(
        self, specifier_string, expected_name, expected_channel_str
    ):
        """Test parsing valid snap specifier strings."""
        snap = SnapSpecifier.from_string(specifier_string)
        assert snap.name == expected_name
        assert str(snap.channel) == expected_channel_str

    @pytest.mark.parametrize(
        "invalid_string,error_pattern",
        [
            ("checkbox", "Cannot parse 'checkbox' as a snap specifier"),
            (
                "checkbox=stable=extra",
                "Cannot parse 'checkbox=stable=extra' as a snap specifier",
            ),
            ("", "Cannot parse '' as a snap specifier"),
        ],
    )
    def test_snap_specifier_from_string_invalid(self, invalid_string, error_pattern):
        """Test that parsing invalid snap specifier strings raises ValueError."""
        with pytest.raises(ValueError, match=error_pattern.replace("=", r"\=")):
            SnapSpecifier.from_string(invalid_string)


class TestSnapSpecifierStringRepresentation:
    """Tests for SnapSpecifier.__str__() method."""

    @pytest.mark.parametrize(
        "name,channel_str,expected_string",
        [
            ("checkbox", "stable", "checkbox=stable"),
            ("checkbox", "latest/stable", "checkbox=latest/stable"),
            ("checkbox", "22/candidate", "checkbox=22/candidate"),
            ("checkbox", "edge/feature", "checkbox=edge/feature"),
            ("checkbox", "22/stable/hotfix", "checkbox=22/stable/hotfix"),
            ("my-snap", "beta", "my-snap=beta"),
        ],
    )
    def test_snap_specifier_str(self, name, channel_str, expected_string):
        """Test string representation of snap specifiers."""
        channel = Channel.from_string(channel_str)
        snap = SnapSpecifier(name=name, channel=channel)
        assert str(snap) == expected_string
