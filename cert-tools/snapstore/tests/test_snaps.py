from pytest import raises, mark

from snapstore.snaps import SnapChannel, SnapSpecifier


class TestSnapChannel:
    """Test cases for the SnapChannel class."""

    @mark.parametrize(
        "channel_str,expected",
        [
            # Risk-only channels
            ("stable", SnapChannel(None, "stable", None)),
            ("candidate", SnapChannel(None, "candidate", None)),
            ("beta", SnapChannel(None, "beta", None)),
            ("edge", SnapChannel(None, "edge", None)),
            # Track-only channels
            ("latest", SnapChannel("latest", None, None)),
            ("2.0", SnapChannel("2.0", None, None)),
            ("my-track", SnapChannel("my-track", None, None)),
            # Track and risk channels
            ("latest/stable", SnapChannel("latest", "stable", None)),
            ("2.0/edge", SnapChannel("2.0", "edge", None)),
            ("my-track/beta", SnapChannel("my-track", "beta", None)),
            # Risk and branch channels (no track)
            ("stable/hotfix", SnapChannel(None, "stable", "hotfix")),
            ("edge/experimental", SnapChannel(None, "edge", "experimental")),
            ("beta/feature", SnapChannel(None, "beta", "feature")),
            # Full channels (track/risk/branch)
            ("latest/stable/hotfix", SnapChannel("latest", "stable", "hotfix")),
            ("2.0/edge/experimental", SnapChannel("2.0", "edge", "experimental")),
            (
                "my-track/beta/feature-branch",
                SnapChannel("my-track", "beta", "feature-branch"),
            ),
        ],
    )
    def test_valid_channel_parsing(self, channel_str, expected):
        """Test parsing valid channel strings and round-trip conversion."""
        channel = SnapChannel.from_string(channel_str)
        assert channel == expected
        assert str(channel) == channel_str

    @mark.parametrize(
        "channel_str",
        [
            # Empty
            "",
            # Too many components
            "invalid/channel/format/extra",
            "track/risk/branch/extra",
            # Invalid characters
            "invalid@channel",
            # Spaces not allowed
            "track with spaces",
            "track/risk with spaces",
        ],
    )
    def test_invalid_channel_formats(self, channel_str):
        """Test that invalid channel formats raise ValueError."""
        with raises(ValueError):
            SnapChannel.from_string(channel_str)


class TestSnapSpecifier:
    """Test cases for the SnapSpecifier class."""

    @mark.parametrize(
        "specifier_str,expected_name,expected_channel",
        [
            # Simple specifiers
            ("mysnap=stable", "mysnap", SnapChannel(None, "stable", None)),
            ("another-snap=edge", "another-snap", SnapChannel(None, "edge", None)),
            ("snap123=latest/beta", "snap123", SnapChannel("latest", "beta", None)),
            # Complex specifiers with full channel specifications
            (
                "mysnap=latest/stable/hotfix",
                "mysnap",
                SnapChannel("latest", "stable", "hotfix"),
            ),
            (
                "app-name=2.0/edge/experimental",
                "app-name",
                SnapChannel("2.0", "edge", "experimental"),
            ),
            ("test=stable/branch", "test", SnapChannel(None, "stable", "branch")),
            # Specifier names with hyphens and numbers
            ("my-snap-name=stable", "my-snap-name", SnapChannel(None, "stable", None)),
            ("snap-123=edge", "snap-123", SnapChannel(None, "edge", None)),
            ("app-v2=latest/beta", "app-v2", SnapChannel("latest", "beta", None)),
        ],
    )
    def test_valid_specifier_parsing(
        self, specifier_str, expected_name, expected_channel
    ):
        """Test parsing valid snap specifiers and round-trip conversion."""
        specifier = SnapSpecifier.from_string(specifier_str)
        assert specifier.name == expected_name
        assert specifier.channel == expected_channel
        assert str(specifier) == specifier_str

    @mark.parametrize(
        "specifier_str",
        [
            # Empty string
            "",
            # Missing channel
            "mysnap=",
            # Missing snap name
            "=channel",
            # Missing = sign
            "no-equals-sign",
            # Double equals
            "snap==channel",
            # Space in snap name
            "snap channel=stable",
        ],
    )
    def test_invalid_specifier_formats(self, specifier_str):
        """Test that invalid specifier formats raise ValueError."""
        with raises(ValueError):
            SnapSpecifier.from_string(specifier_str)
