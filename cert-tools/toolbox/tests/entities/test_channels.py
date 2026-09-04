"""Tests for Channel and Risk entities."""

import pytest

from toolbox.entities.channels import Channel, Risk


class TestRisk:
    """Tests for Risk enum."""

    @pytest.mark.parametrize(
        "risk_value",
        ["stable", "candidate", "beta", "edge"],
    )
    def test_risk_enum_values(self, risk_value):
        """Test that all risk levels are valid enum values."""
        risk = Risk(risk_value)
        assert risk.value == risk_value

    @pytest.mark.parametrize(
        "input_value,expected",
        [
            ("stable", True),
            ("candidate", True),
            ("beta", True),
            ("edge", True),
            ("STABLE", True),
            ("Candidate", True),
            ("invalid", False),
            ("", False),
            ("unknown", False),
        ],
    )
    def test_risk_validate(self, input_value, expected):
        """Test Risk.validate() with various inputs."""
        assert Risk.validate(input_value) == expected


class TestChannelInitialization:
    """Tests for Channel initialization."""

    def test_channel_with_track_only(self):
        """Test creating a channel with only a track."""
        channel = Channel(track="latest")
        assert channel.track == "latest"
        assert channel.risk is None
        assert channel.branch is None

    def test_channel_with_risk_only(self):
        """Test creating a channel with only a risk."""
        channel = Channel(risk="stable")
        assert channel.track is None
        assert channel.risk == "stable"
        assert channel.branch is None

    def test_channel_with_track_and_risk(self):
        """Test creating a channel with track and risk."""
        channel = Channel(track="22", risk="stable")
        assert channel.track == "22"
        assert channel.risk == "stable"
        assert channel.branch is None

    def test_channel_with_all_components(self):
        """Test creating a channel with track, risk, and branch."""
        channel = Channel(track="22", risk="stable", branch="hotfix")
        assert channel.track == "22"
        assert channel.risk == "stable"
        assert channel.branch == "hotfix"

    def test_channel_with_no_components_raises_error(self):
        """Test that creating a channel with no components raises ValueError."""
        with pytest.raises(
            ValueError, match="At least one of track or risk must be set"
        ):
            Channel()

    def test_channel_with_invalid_risk_raises_error(self):
        """Test that creating a channel with invalid risk raises ValueError."""
        with pytest.raises(ValueError, match="'invalid' is not a valid risk"):
            Channel(risk="invalid")


class TestChannelFromString:
    """Tests for Channel.from_string() method."""

    @pytest.mark.parametrize(
        "channel_string,expected_track,expected_risk,expected_branch",
        [
            # risk only
            ("stable", None, "stable", None),
            ("candidate", None, "candidate", None),
            ("beta", None, "beta", None),
            ("edge", None, "edge", None),
            # track only
            ("latest", "latest", None, None),
            ("22", "22", None, None),
            ("20/stable", "20", "stable", None),
            # track and risk
            ("latest/stable", "latest", "stable", None),
            ("22/candidate", "22", "candidate", None),
            ("1.0/beta", "1.0", "beta", None),
            # track, risk, and branch
            ("latest/stable/hotfix", "latest", "stable", "hotfix"),
            ("22/edge/feature-x", "22", "edge", "feature-x"),
            # risk and branch (no track)
            ("stable/hotfix", None, "stable", "hotfix"),
            ("edge/my-branch", None, "edge", "my-branch"),
        ],
    )
    def test_channel_from_string_valid(
        self, channel_string, expected_track, expected_risk, expected_branch
    ):
        """Test parsing valid channel strings."""
        channel = Channel.from_string(channel_string)
        assert channel.track == expected_track
        assert channel.risk == expected_risk
        assert channel.branch == expected_branch

    def test_channel_from_string_empty_raises_error(self):
        """Test that parsing empty string raises ValueError."""
        with pytest.raises(
            ValueError, match="At least one of track or risk must be set"
        ):
            Channel.from_string("")

    def test_channel_from_string_invalid_risk_raises_error(self):
        """Test that parsing string with invalid risk raises ValueError."""
        with pytest.raises(ValueError, match="'invalid-risk' is not a valid risk"):
            Channel.from_string("track/invalid-risk")

    def test_channel_from_string_too_many_components_raises_error(self):
        """Test that parsing string with too many components raises ValueError."""
        with pytest.raises(ValueError, match="Cannot parse .* as a snap channel"):
            Channel.from_string("stable/candidate/beta/extra")


class TestChannelStringRepresentation:
    """Tests for Channel.__str__() method."""

    @pytest.mark.parametrize(
        "track,risk,branch,expected_string",
        [
            (None, "stable", None, "stable"),
            ("latest", None, None, "latest"),
            ("latest", "stable", None, "latest/stable"),
            ("22", "candidate", None, "22/candidate"),
            ("latest", "stable", "hotfix", "latest/stable/hotfix"),
            (None, "edge", "feature", "edge/feature"),
        ],
    )
    def test_channel_str(self, track, risk, branch, expected_string):
        """Test string representation of channels."""
        channel = Channel(track=track, risk=risk, branch=branch)
        assert str(channel) == expected_string
