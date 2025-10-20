from argparse import ArgumentParser, Namespace
import json
from typing import List

from snapstore.craft import create_base_client
from snapstore.client import SnapstoreClient
from snapstore.info import SnapstoreInfo
from snapstore.snaps import SnapSpecifier, SnapChannel


def get_info_arguments(args: List[str] | None = None) -> Namespace:
    parser = ArgumentParser(description="Retrieve snap info from the Store")
    parser.add_argument("snap", type=str)
    parser.add_argument("channel", type=str)
    parser.add_argument("architecture", type=str)
    parser.add_argument("--store", type=str)
    parser.add_argument(
        "--fields",
        nargs="+",
        help=(
            "fields to include in the response "
            "(see https://api.snapcraft.io/docs/refresh.html "
            "or https://api.snapcraft.io/docs/info.html)"
        ),
    )
    parser.add_argument(
        "--use-info",
        dest="refresh",
        action="store_false",
        help="use `v2/snaps/info` endpoint (default is `v2/snaps/refresh`)",
    )
    parser.add_argument(
        "--token-environment-variable",
        dest="variable",
        type=str,
        default="UBUNTU_STORE_AUTH",
        help="Variable containing token returned by `snapcraft export-login`",
    )
    return parser.parse_args(args)


def _get_snap_info(info: SnapstoreInfo, args: Namespace) -> dict:
    """
    Return info for a specific snap. Use the `v2/snaps/info/{snap}`
    endpoint of the snap Store API and return the entry from the
    channel map that matches a specific channel and architecture.
    """
    snap = args.snap
    channel = SnapChannel.from_string(args.channel)
    architecture = args.architecture
    store = args.store
    fields = args.fields

    response = info.get_snap_info(
        snap=snap,
        architecture=architecture,
        store=store,
        fields=fields,
    )

    # locate the matching channel entry in the channel map and return it
    for entry in response["channel-map"]:
        channel_dict = entry["channel"]
        if (
            channel_dict["track"] == channel.track
            and channel_dict["risk"] == channel.risk
        ):
            return entry

    # no matching entry
    raise ValueError(f"No info for {snap}={channel} on {architecture}")


def _get_refresh_info(info: SnapstoreInfo, args: Namespace) -> dict:
    """
    Return info for a specific snap. Use the `v2/snaps/refresh`
    endpoint of the snap Store API and return the "snap" field of the
    result, along with the "effective channel".
    """
    snap = SnapSpecifier.from_string(f"{args.snap}={args.channel}")
    architecture = args.architecture
    store = args.store
    fields = args.fields

    response = info.get_refresh_info(
        snap_specifiers=[snap],
        architecture=architecture,
        store=store,
        fields=fields,
    )

    # extract what should be a single result from the response
    if len(response) != 1:
        raise ValueError(f"Multiple results for {snap} on {architecture}")
    result = response[0]

    # check for errors
    if result["result"] == "error":
        raise ValueError(f"{snap}@{architecture}: {result['error']['message']}")

    # process and return the result
    return {**result["snap"], **{"effective-channel": result["effective-channel"]}}


def info_cli():
    args = get_info_arguments()
    base_client = create_base_client(token_environment_variable=args.variable)
    client = SnapstoreClient(base_client)
    info = SnapstoreInfo(client)
    if args.refresh:
        result = _get_refresh_info(info, args)
    else:
        result = _get_snap_info(info, args)

    # display as JSON so that the result can be parsed with jq
    print(json.dumps(result))
