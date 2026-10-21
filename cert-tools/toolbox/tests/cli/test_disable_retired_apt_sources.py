"""Tests for the disable-retired-apt-sources CLI."""

import pytest
from invoke import Result

from toolbox.cli import disable_retired_apt_sources as cli
from toolbox.cli.disable_retired_apt_sources import (
    MARKER,
    clean_classic_sources,
    clean_deb822_sources,
    clean_source_file,
    host_of,
    is_retired_uri,
    main,
    source_uri,
)

SOURCES_LIST = """\

deb http://archive.ubuntu.com/ubuntu/ focal main restricted
# deb-src http://archive.ubuntu.com/ubuntu/ focal main restricted

## This software is not part of Ubuntu, but is offered by Canonical and the
## respective vendors as a service to Ubuntu users.
deb http://archive.canonical.com/ubuntu focal partner
# deb-src http://archive.canonical.com/ubuntu focal partner

deb http://security.ubuntu.com/ubuntu focal-security main restricted
"""

DEB822 = """\
Types: deb
URIs: http://archive.canonical.com/ubuntu
Suites: focal
Components: partner
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg

Types: deb
URIs: http://oem.archive.canonical.com/
Suites: focal
Components: oem
"""


@pytest.mark.parametrize(
    "line, expected",
    [
        (
            "deb http://archive.canonical.com/ubuntu focal partner",
            "http://archive.canonical.com/ubuntu",
        ),
        (
            "deb-src http://archive.canonical.com/ubuntu focal partner",
            "http://archive.canonical.com/ubuntu",
        ),
        (
            "deb [arch=amd64] http://archive.ubuntu.com/ubuntu focal main",
            "http://archive.ubuntu.com/ubuntu",
        ),
        (
            "deb [ arch=amd64 ] http://example.com/ubuntu focal main",
            "http://example.com/ubuntu",
        ),
        ("# deb http://archive.canonical.com/ubuntu focal partner", ""),
        ("", ""),
        ("## comment", ""),
        ("deb", ""),
    ],
)
def test_source_uri(line, expected):
    assert source_uri(line) == expected


@pytest.mark.parametrize(
    "uri, expected",
    [
        ("http://archive.canonical.com/ubuntu", True),
        ("http://ARCHIVE.CANONICAL.COM/ubuntu", True),
        ("http://oem.archive.canonical.com/", False),
        ("http://dell.archive.canonical.com/", False),
        ("http://archive.ubuntu.com/ubuntu", False),
        ("", False),
    ],
)
def test_is_retired_uri(uri, expected):
    assert is_retired_uri(uri) is expected


def test_host_of():
    assert host_of("http://archive.canonical.com/ubuntu") == "archive.canonical.com"
    assert host_of("") == ""


def test_clean_classic_sources_comments_the_partner_line():
    cleaned, disabled = clean_classic_sources(SOURCES_LIST)

    assert disabled == 1
    assert (
        f"{MARKER}\n# deb http://archive.canonical.com/ubuntu focal partner" in cleaned
    )
    # the commented deb-src line is left untouched
    assert "# deb-src http://archive.canonical.com/ubuntu focal partner" in cleaned
    # nothing else changes
    assert "deb http://archive.ubuntu.com/ubuntu/ focal main restricted" in cleaned
    assert (
        "deb http://security.ubuntu.com/ubuntu focal-security main restricted"
        in cleaned
    )


def test_clean_classic_sources_is_idempotent():
    cleaned, disabled = clean_classic_sources(SOURCES_LIST)
    again, disabled_again = clean_classic_sources(cleaned)

    assert disabled == 1
    assert disabled_again == 0
    assert again == cleaned


def test_clean_classic_sources_leaves_the_oem_archives_alone():
    text = (
        "deb http://oem.archive.canonical.com/ focal oem\n"
        "deb http://dell.archive.canonical.com/ focal somerville\n"
    )
    cleaned, disabled = clean_classic_sources(text)

    assert disabled == 0
    assert cleaned == text


def test_clean_deb822_sources_disables_the_retired_stanza():
    cleaned, disabled = clean_deb822_sources(DEB822)

    assert disabled == 1
    assert "URIs: http://archive.canonical.com/ubuntu\nEnabled: no\n" in cleaned
    # the unrelated OEM archive stanza is untouched
    assert (
        "Types: deb\nURIs: http://oem.archive.canonical.com/\nSuites: focal" in cleaned
    )


def test_clean_deb822_sources_replaces_an_enabled_yes():
    text = "Types: deb\nURIs: http://archive.canonical.com/ubuntu\nEnabled: yes\n"
    cleaned, disabled = clean_deb822_sources(text)

    assert disabled == 1
    assert (
        cleaned
        == "Types: deb\nURIs: http://archive.canonical.com/ubuntu\nEnabled: no\n"
    )


def test_clean_deb822_sources_is_idempotent():
    cleaned, _ = clean_deb822_sources(DEB822)
    again, disabled = clean_deb822_sources(cleaned)

    assert disabled == 0
    assert again == cleaned


def test_clean_deb822_sources_handles_multiline_uris():
    text = (
        "Types: deb\n"
        "URIs: http://archive.ubuntu.com/ubuntu\n"
        "      http://archive.canonical.com/ubuntu\n"
        "Suites: focal\n"
    )
    cleaned, disabled = clean_deb822_sources(text)

    assert disabled == 1
    assert (
        "      http://archive.canonical.com/ubuntu\nEnabled: no\nSuites: focal\n"
        in cleaned
    )


def test_clean_source_file_dispatches_on_suffix():
    assert clean_source_file("/etc/apt/sources.list", SOURCES_LIST)[1] == 1
    assert clean_source_file("/etc/apt/sources.list.d/x.list", SOURCES_LIST)[1] == 1
    assert clean_source_file("/etc/apt/sources.list.d/x.sources", DEB822)[1] == 1


def _device(
    mocker,
    listing="focal-oem.list\ngoogle-chrome.sources\n",
    files=None,
    write_failed=False,
):
    files = files or {}
    device = mocker.Mock()
    device.host = "10.0.0.1"

    def run(command, **kwargs):
        if command[:2] == ["ls", "-1"]:
            return Result(stdout=listing, exited=0)
        path = command[-1]
        if path not in files:
            return Result(stdout="", exited=1, stderr="No such file")
        return Result(stdout=files[path], exited=0)

    device.run.side_effect = run
    device.write_remote_file.return_value = Result(exited=1 if write_failed else 0)
    mocker.patch.object(cli, "LabDevice", return_value=device)
    return device


def test_main_disables_the_retired_source(mocker, capsys):
    files = {
        "/etc/apt/sources.list": SOURCES_LIST,
        "/etc/apt/sources.list.d/focal-oem.list": "deb http://oem.archive.canonical.com/ focal oem\n",
        "/etc/apt/sources.list.d/google-chrome.sources": "Types: deb\nURIs: http://dl.google.com/linux/chrome/deb/\n",
    }
    device = _device(mocker, files=files)
    mocker.patch("sys.argv", ["disable-retired-apt-sources"])

    main()

    out = capsys.readouterr().out
    assert "Disabled 1 retired source(s) in /etc/apt/sources.list" in out
    device.write_remote_file.assert_called_once()
    path, content = device.write_remote_file.call_args.args
    assert path == "/etc/apt/sources.list"
    assert MARKER in content


def test_main_reports_when_nothing_is_retired(mocker, capsys):
    files = {
        "/etc/apt/sources.list": "deb http://archive.ubuntu.com/ubuntu focal main\n"
    }
    device = _device(mocker, listing="", files=files)
    mocker.patch("sys.argv", ["disable-retired-apt-sources"])

    main()

    out = capsys.readouterr().out
    assert "No retired APT sources found on 10.0.0.1." in out
    device.write_remote_file.assert_not_called()


def test_main_skips_an_unreadable_file(mocker, capsys):
    device = _device(mocker, listing="missing.list", files={})
    mocker.patch("sys.argv", ["disable-retired-apt-sources"])

    main()

    out = capsys.readouterr().out
    assert "SKIP: cannot read /etc/apt/sources.list.d/missing.list" in out
    device.write_remote_file.assert_not_called()


def test_main_reports_a_write_failure(mocker, capsys):
    files = {"/etc/apt/sources.list": SOURCES_LIST}
    device = _device(mocker, listing="", files=files, write_failed=True)
    mocker.patch("sys.argv", ["disable-retired-apt-sources"])

    main()

    out = capsys.readouterr().out
    assert "ERROR: failed to write /etc/apt/sources.list on 10.0.0.1" in out
    device.write_remote_file.assert_called_once()


def test_main_dry_run_does_not_write(mocker, capsys):
    files = {"/etc/apt/sources.list": SOURCES_LIST}
    device = _device(mocker, listing="", files=files)
    mocker.patch("sys.argv", ["disable-retired-apt-sources", "--dry-run"])

    main()

    out = capsys.readouterr().out
    assert "Would disable 1 retired source(s) in /etc/apt/sources.list" in out
    device.write_remote_file.assert_not_called()


def test_main_exits_1_without_device_ip(mocker, capsys):
    mocker.patch.object(
        cli, "LabDevice", side_effect=RuntimeError("Host is unspecified")
    )
    mocker.patch("sys.argv", ["disable-retired-apt-sources"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    assert "ERROR: Host is unspecified" in capsys.readouterr().out
