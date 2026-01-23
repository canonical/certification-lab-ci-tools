"""Tests for CheckboxRuntimeHelper."""

import pytest

from toolbox.checkbox.helpers.runtime import CheckboxRuntimeHelper
from toolbox.entities.channels import Channel
from toolbox.entities.snaps import SnapSpecifier


class TestCheckboxRuntimeHelper:
    """Tests for CheckboxRuntimeHelper."""

    @pytest.mark.parametrize(
        "base,expected_runtime",
        [
            (None, "checkbox16"),
            ("core", "checkbox16"),
            ("core16", "checkbox16"),
            ("core18", "checkbox18"),
            ("core20", "checkbox20"),
            ("core22", "checkbox22"),
            ("core24", "checkbox24"),
        ],
    )
    def test_determine_checkbox_runtime_name(self, base, expected_runtime):
        """Test determining Checkbox runtime name from base snap."""
        result = CheckboxRuntimeHelper.determine_checkbox_runtime_name(base)
        assert result == expected_runtime

    def test_determine_checkbox_runtime_name_invalid_base(self):
        """Test that invalid base snap raises ValueError."""
        with pytest.raises(ValueError, match="Unable to determine base suffix"):
            CheckboxRuntimeHelper.determine_checkbox_runtime_name("invalid-base")

    def test_get_base_success(self, mocker):
        """Test getting base snap successfully."""
        mock_device = mocker.Mock()
        mock_snapstore = mocker.Mock()
        mock_info = mocker.Mock()

        response = [
            {
                "result": "refresh",
                "snap": {"base": "core22", "name": "checkbox"},
            }
        ]
        mock_info.get_refresh_info.return_value = response

        mocker.patch(
            "toolbox.checkbox.helpers.runtime.SnapstoreInfo", return_value=mock_info
        )

        helper = CheckboxRuntimeHelper(mock_device, mock_snapstore)
        snap = SnapSpecifier(name="checkbox", channel=Channel(risk="stable"))

        base = helper.get_base(snap, "amd64", "ubuntu")

        assert base == "core22"
        mock_info.get_refresh_info.assert_called_once_with(
            snap_specifiers=[snap],
            architecture="amd64",
            store="ubuntu",
            fields=["base"],
        )

    def test_get_base_no_base(self, mocker):
        """Test getting base when snap has no base."""
        mock_device = mocker.Mock()
        mock_snapstore = mocker.Mock()
        mock_info = mocker.Mock()

        response = [
            {
                "result": "refresh",
                "snap": {"name": "checkbox"},
            }
        ]
        mock_info.get_refresh_info.return_value = response

        mocker.patch(
            "toolbox.checkbox.helpers.runtime.SnapstoreInfo", return_value=mock_info
        )

        helper = CheckboxRuntimeHelper(mock_device, mock_snapstore)
        snap = SnapSpecifier(name="checkbox", channel=Channel(risk="stable"))

        base = helper.get_base(snap, "amd64", "ubuntu")

        assert base is None

    def test_get_base_multiple_results(self, mocker):
        """Test that multiple results raise ValueError."""
        mock_device = mocker.Mock()
        mock_snapstore = mocker.Mock()
        mock_info = mocker.Mock()

        response = [
            {"result": "refresh", "snap": {"base": "core22"}},
            {"result": "refresh", "snap": {"base": "core20"}},
        ]
        mock_info.get_refresh_info.return_value = response

        mocker.patch(
            "toolbox.checkbox.helpers.runtime.SnapstoreInfo", return_value=mock_info
        )

        helper = CheckboxRuntimeHelper(mock_device, mock_snapstore)
        snap = SnapSpecifier(name="checkbox", channel=Channel(risk="stable"))

        with pytest.raises(ValueError, match="Multiple results"):
            helper.get_base(snap, "amd64", "ubuntu")

    def test_get_base_error_response(self, mocker):
        """Test that error response raises ValueError."""
        mock_device = mocker.Mock()
        mock_snapstore = mocker.Mock()
        mock_info = mocker.Mock()

        response = [
            {
                "result": "error",
                "error": {"message": "Snap not found"},
            }
        ]
        mock_info.get_refresh_info.return_value = response

        mocker.patch(
            "toolbox.checkbox.helpers.runtime.SnapstoreInfo", return_value=mock_info
        )

        helper = CheckboxRuntimeHelper(mock_device, mock_snapstore)
        snap = SnapSpecifier(name="checkbox", channel=Channel(risk="stable"))

        with pytest.raises(ValueError, match="Snap not found"):
            helper.get_base(snap, "amd64", "ubuntu")

    def test_get_base_error_response_with_store(self, mocker):
        """Test that error response includes store in message."""
        mock_device = mocker.Mock()
        mock_snapstore = mocker.Mock()
        mock_info = mocker.Mock()

        response = [
            {
                "result": "error",
                "error": {"message": "Snap not found"},
            }
        ]
        mock_info.get_refresh_info.return_value = response

        mocker.patch(
            "toolbox.checkbox.helpers.runtime.SnapstoreInfo", return_value=mock_info
        )

        helper = CheckboxRuntimeHelper(mock_device, mock_snapstore)
        snap = SnapSpecifier(name="checkbox", channel=Channel(risk="stable"))

        with pytest.raises(ValueError, match="from branded-store"):
            helper.get_base(snap, "amd64", "branded-store")

    def test_determine_checkbox_runtime_core22(self, mocker):
        """Test determining Checkbox runtime for core22-based snap."""
        mock_device = mocker.Mock()
        mock_snapstore = mocker.Mock()
        mock_info = mocker.Mock()

        response = [
            {
                "result": "refresh",
                "snap": {"base": "core22"},
            }
        ]
        mock_info.get_refresh_info.return_value = response

        mocker.patch(
            "toolbox.checkbox.helpers.runtime.SnapstoreInfo", return_value=mock_info
        )

        helper = CheckboxRuntimeHelper(mock_device, mock_snapstore)
        snap = SnapSpecifier(name="checkbox", channel=Channel.from_string("22/stable"))

        runtime = helper.determine_checkbox_runtime(snap, "amd64", "ubuntu")

        assert runtime.name == "checkbox22"
        assert runtime.channel.track == "latest"
        assert runtime.channel.risk == "stable"

    def test_determine_checkbox_runtime_preserves_risk(self, mocker):
        """Test that risk level is preserved in runtime snap channel."""
        mock_device = mocker.Mock()
        mock_snapstore = mocker.Mock()
        mock_info = mocker.Mock()

        response = [
            {
                "result": "refresh",
                "snap": {"base": "core20"},
            }
        ]
        mock_info.get_refresh_info.return_value = response

        mocker.patch(
            "toolbox.checkbox.helpers.runtime.SnapstoreInfo", return_value=mock_info
        )

        helper = CheckboxRuntimeHelper(mock_device, mock_snapstore)
        snap = SnapSpecifier(name="checkbox", channel=Channel.from_string("22/edge"))

        runtime = helper.determine_checkbox_runtime(snap, "amd64", "ubuntu")

        assert runtime.name == "checkbox20"
        assert runtime.channel.track == "latest"
        assert runtime.channel.risk == "edge"

    def test_init_creates_snapstore_info(self, mocker):
        """Test that __init__ creates SnapstoreInfo with the provided client."""
        mock_device = mocker.Mock()
        mock_snapstore = mocker.Mock()
        mock_info = mocker.Mock()

        mock_info_class = mocker.patch(
            "toolbox.checkbox.helpers.runtime.SnapstoreInfo", return_value=mock_info
        )

        helper = CheckboxRuntimeHelper(mock_device, mock_snapstore)

        assert helper.device is mock_device
        assert helper.info is mock_info
        mock_info_class.assert_called_once_with(mock_snapstore)
