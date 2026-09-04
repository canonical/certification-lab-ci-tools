from pytest import fixture, mark, raises

from snapstore.client import SnapstoreClient
from snapstore.info import SnapstoreInfo
from snapstore.snaps import SnapSpecifier


class TestSnapstoreInfo:
    """Test suite for SnapstoreInfo class."""

    @fixture
    def mock_client(self, mocker):
        """Create a mock SnapstoreClient."""
        return mocker.create_autospec(SnapstoreClient, instance=True)

    @fixture
    def snapstore_info(self, mock_client):
        """Create SnapstoreInfo instance with mocked client."""
        return SnapstoreInfo(mock_client)

    def test_client_exceptions_propagate(self, snapstore_info):
        """Test that exceptions from client methods propagate correctly."""
        snapstore_info.client.get.side_effect = Exception("API Error")

        with raises(Exception, match="API Error"):
            snapstore_info.get_snap_info("snap")

    class TestGetSnapInfo:
        """Test cases for get_snap_info method."""

        @mark.parametrize(
            "architecture, store, fields",
            [
                (None, None, None),
                ("amd64", None, None),
                (None, "ubuntu", None),
                (None, None, ["version", "revision"]),
                ("amd64", "ubuntu", None),
                (None, "ubuntu", ["base"]),
                ("amd64", None, ["version", "revision"]),
                ("amd64", "ubuntu", ["version", "revision"]),
                ("amd64", "ubuntu", []),
            ],
        )
        def test_get_snap_info(self, snapstore_info, architecture, store, fields):
            """Test get_snap_info with all parameters provided."""
            name = "test-snap"
            expected_response = {"name": name, "channel-map": []}
            snapstore_info.client.get.return_value = expected_response
            expected_params = {}
            if architecture is not None:
                expected_params["architecture"] = architecture
            if fields:
                expected_params["fields"] = ",".join(fields)

            result = snapstore_info.get_snap_info(
                snap=name, architecture=architecture, store=store, fields=fields
            )

            snapstore_info.client.get.assert_called_once_with(
                endpoint=f"v2/snaps/info/{name}",
                params=expected_params,
                store=store,
            )
            assert result == expected_response

    class TestGetRefreshInfo:
        """Test cases for get_refresh_info method."""

        @mark.parametrize(
            "snap_specifier_strings, store, fields",
            [
                (["snap-1=latest/beta", "snap-2=latest/edge"], None, None),
                (["snap-1=latest/beta", "snap-2=latest/edge"], "ubuntu", None),
                (["snap-1=latest/beta", "snap-2=latest/edge"], None, ["base"]),
                (["snap-1=latest/beta"], "ubuntu", ["version", "revision"]),
            ],
        )
        def test_get_refresh_info(
            self, snapstore_info, snap_specifier_strings, store, fields
        ):
            """Test get_refresh_info with minimal required parameters."""
            snap_specifiers = [
                SnapSpecifier.from_string(snap_specifier)
                for snap_specifier in snap_specifier_strings
            ]
            expected_response = {
                "results": [
                    {"name": snap_specifier.name, "result": "download"}
                    for snap_specifier in snap_specifiers
                ]
            }
            snapstore_info.client.post.return_value = expected_response
            expected_payload = {
                "context": [],
                "actions": [
                    {
                        "name": snap_specifier.name,
                        "channel": str(snap_specifier.channel),
                        "action": "download",
                        "instance-key": snap_specifier.name,
                    }
                    for snap_specifier in snap_specifiers
                ],
            }
            if fields:
                expected_payload["fields"] = sorted(fields)

            result = snapstore_info.get_refresh_info(
                snap_specifiers=snap_specifiers,
                architecture="amd64",
                store=store,
                fields=fields,
            )

            snapstore_info.client.post.assert_called_once_with(
                endpoint="v2/snaps/refresh",
                payload=expected_payload,
                store=store,
                headers={"Snap-Device-Architecture": "amd64"},
            )
            assert result == expected_response["results"]
