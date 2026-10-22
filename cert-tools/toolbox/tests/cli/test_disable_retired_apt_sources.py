"""Tests for the disable-retired-apt-sources CLI."""

import pytest
from invoke import Result

from toolbox.cli import disable_retired_apt_sources as cli
from toolbox.cli.disable_retired_apt_sources import MARKER, comment_out, is_retired

SOURCES_LIST = """\
deb http://archive.ubuntu.com/ubuntu/ focal main restricted
# deb http://archive.canonical.com/ubuntu focal partner
deb http://archive.canonical.com/ubuntu focal partner
deb http://oem.archive.canonical.com/ focal oem
deb http://dell.archive.canonical.com/ focal somerville
"""


@pytest.mark.parametrize(
    "line, expected",
    [
        ("deb http://archive.canonical.com/ubuntu focal partner", True),
        ("deb-src http://archive.canonical.com/ubuntu focal partner", True),
        ("deb http://oem.archive.canonical.com/ focal oem", False),
        ("deb http://dell.archive.canonical.com/ focal somerville", False),
        ("# deb http://archive.canonical.com/ubuntu focal partner", False),
        ("deb http://archive.ubuntu.com/ubuntu/ focal main", False),
    ],
)
def test_is_retired(line, expected):
    assert is_retired(line) is expected


def test_comment_out_only_touches_the_retired_entry():
    cleaned, changed = comment_out(SOURCES_LIST)

    assert changed == 1
    assert f"{MARKER}deb http://archive.canonical.com/ubuntu focal partner" in cleaned
    assert "deb http://oem.archive.canonical.com/ focal oem" in cleaned
    assert "deb http://dell.archive.canonical.com/ focal somerville" in cleaned


def test_comment_out_is_idempotent():
    cleaned, _ = comment_out(SOURCES_LIST)
    again, changed = comment_out(cleaned)

    assert changed == 0
    assert again == cleaned


def _device(mocker, listing="focal-oem.list", files=None):
    device = mocker.Mock()
    device.host = "10.0.0.1"

    def run(command, **kwargs):
        if command[:2] == ["ls", "-1"]:
            return Result(stdout=listing, exited=0)
        return Result(stdout=files.get(command[-1], ""), exited=0)

    device.run.side_effect = run
    mocker.patch.object(cli, "LabDevice", return_value=device)
    return device


def test_main_comments_out_and_reports(mocker, capsys):
    device = _device(mocker, files={"/etc/apt/sources.list": SOURCES_LIST})

    cli.main()

    assert "commented out 1 retired source(s)" in capsys.readouterr().out
    device.write_remote_file.assert_called_once()
    assert device.write_remote_file.call_args.args[0] == "/etc/apt/sources.list"


def test_main_writes_nothing_when_there_is_no_retired_source(mocker, capsys):
    device = _device(
        mocker,
        files={
            "/etc/apt/sources.list": "deb http://archive.ubuntu.com/ubuntu focal main\n"
        },
    )

    cli.main()

    assert "10.0.0.1: 0 retired source(s) disabled" in capsys.readouterr().out
    device.write_remote_file.assert_not_called()
