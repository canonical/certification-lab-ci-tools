from pytest import mark, raises

from snapstore.info import SnapstoreInfo
from snapstore.cli import get_info_arguments, _get_snap_info, _get_refresh_info


class TestGetInfoArguments:
    """Test the argument parsing function."""

    def test_required_arguments(self):
        """Test parsing of required arguments."""
        command_line = ["test-snap", "stable", "amd64"]
        args = get_info_arguments(command_line)
        assert args.snap == command_line[0]
        assert args.channel == command_line[1]
        assert args.architecture == command_line[2]
        assert args.fields is None
        assert args.store is None
        assert args.refresh is True
        assert args.variable == "UBUNTU_STORE_AUTH"

    def test_optional_store_argument(self):
        """Test parsing of optional --store argument."""
        store_name = "ubuntu"
        command_line = ["test-snap", "stable", "amd64", "--store", store_name]
        args = get_info_arguments(command_line)
        assert args.store == store_name

    @mark.parametrize("fields", [["base"], ["version", "revision"]])
    def test_optional_fields_argument(self, fields):
        """Test parsing of optional --fields argument."""
        command_line = ["test-snap", "stable", "amd64", "--fields"] + fields
        args = get_info_arguments(command_line)
        assert args.fields == fields

    def test_empty_fields(self):
        """Test parsing of optional --fields argument."""
        command_line = ["test-snap", "stable", "amd64", "--fields"]
        with raises(SystemExit):
            get_info_arguments(command_line)

    def test_use_info_flag(self):
        """Test the --use-info flag sets refresh to appropriate value."""
        command_line = ["test-snap", "stable", "amd64"]
        args = get_info_arguments(command_line)
        assert args.refresh is True
        args = get_info_arguments(command_line + ["--use-info"])
        assert args.refresh is False

    def test_custom_token_environment_variable(self):
        """Test custom token environment variable."""
        token_environmnent_variable = "CREDENTIALS"
        command_line = [
            "test-snap",
            "stable",
            "amd64",
            "--token-environment-variable",
            token_environmnent_variable,
        ]
        args = get_info_arguments(command_line)
        assert args.variable == token_environmnent_variable


class TestGetSnapInfo:
    """Test the get_snap_info function."""

    def test_successful_channel_match(self, mocker):
        """Test successful retrieval when channel matches."""
        command_line = ["test-snap", "latest/beta", "arm64"]
        args = get_info_arguments(command_line)
        info = mocker.create_autospec(SnapstoreInfo, instance=True)
        info.get_snap_info.return_value = {
            "channel-map": [
                {
                    "channel": {"track": "latest", "risk": "beta"},
                    "revision": 123,
                    "version": "1.0.0",
                },
                {
                    "channel": {"track": "latest", "risk": "edge"},
                    "revision": 124,
                    "version": "1.0.1",
                },
            ]
        }

        result = _get_snap_info(info, args)

        assert result == {
            "channel": {"track": "latest", "risk": "beta"},
            "revision": 123,
            "version": "1.0.0",
        }

    def test_no_matching_channel(self, mocker):
        """Test ValueError when no matching channel is found."""

        command_line = ["test-snap", "latest/beta", "arm64"]
        args = get_info_arguments(command_line)
        info = mocker.create_autospec(SnapstoreInfo, instance=True)
        info.get_snap_info.return_value = {
            "channel-map": [
                {
                    "channel": {"track": "latest", "risk": "stable"},
                    "revision": 123,
                    "version": "1.0.0",
                },
                {
                    "channel": {"track": "latest", "risk": "edge"},
                    "revision": 124,
                    "version": "1.0.1",
                },
            ]
        }

        with raises(ValueError):
            _get_snap_info(info, args)


class TestGetRefreshInfo:
    """Test the get_refresh_info function."""

    def test_successful_refresh(self, mocker):
        """Test successful refresh info retrieval."""
        command_line = ["test-snap", "latest/beta", "arm64"]
        args = get_info_arguments(command_line)
        info = mocker.create_autospec(SnapstoreInfo, instance=True)
        info.get_refresh_info.return_value = [
            {
                "result": "refresh",
                "snap": {"revision": 123, "version": "1.0.0", "name": "test-snap"},
                "effective-channel": "latest/stable",
            }
        ]

        result = _get_refresh_info(info, args)

        expected_result = {
            "revision": 123,
            "version": "1.0.0",
            "name": "test-snap",
            "effective-channel": "latest/stable",
        }
        assert result == expected_result

    def test_error(self, mocker):
        """Test ValueError when result contains error."""
        command_line = ["test-snap", "latest/beta", "arm64"]
        args = get_info_arguments(command_line)
        error_message = "The Snap with the given name was not found in the Store."
        info = mocker.create_autospec(SnapstoreInfo, instance=True)
        info.get_refresh_info.return_value = [
            {"result": "error", "error": {"message": error_message}}
        ]

        with raises(ValueError, match=error_message):
            _get_refresh_info(info, args)
