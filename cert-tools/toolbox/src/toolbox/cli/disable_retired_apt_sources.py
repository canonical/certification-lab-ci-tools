"""Disable retired APT sources on the device under test.

``archive.canonical.com`` served the *partner* component for bionic, focal and
xenial. It has been retired upstream, so any ``apt-get update`` that references
it fails::

    E: Failed to fetch http://archive.canonical.com/ubuntu/dists/focal/InRelease
       500  Remote or cache error [IP: 10.15.22.2 3142]
    E: The repository 'http://archive.canonical.com/ubuntu focal InRelease'
       is no longer signed.

The line ships in the OEM images the lab reprovisions, so it comes back after
every provisioning and aborts the run before any test starts.

This CLI reads the APT source files of the device over SSH, computes the
cleaned content on the agent, and writes it back only when it changed:

* classic one-line files (``sources.list``, ``sources.list.d/*.list``) get the
  offending line commented out, with a marker line above it;
* deb822 files (``sources.list.d/*.sources``) get ``Enabled: no`` in the
  stanza that references a retired host.

Only the exact retired hosts are touched: ``oem.archive.canonical.com`` and
``dell.archive.canonical.com`` are still served and keep working.

Every step is idempotent. A file without a retired host is not rewritten, a
commented line is not commented twice and a stanza that is already disabled is
left alone. Read failures and write failures are reported and do not abort the
run, so a cleanup problem never fails a test job.

The device IP is provided by the environment variable ``DEVICE_IP``; the user
name defaults to ``ubuntu`` (``DEVICE_USER``) and password authentication is
used when ``DEVICE_PWD`` is set, exactly like the other device CLIs.

Usage::

    DEVICE_IP=<dut-ip> disable-retired-apt-sources
    DEVICE_IP=<dut-ip> disable-retired-apt-sources --dry-run
"""

import sys
from argparse import ArgumentParser
from urllib.parse import urlparse

from toolbox.devices.lab import LabDevice

#: Hosts that no longer serve their archives.
RETIRED_HOSTS = ("archive.canonical.com",)

#: Line written above every source line that gets commented out.
MARKER = "# disabled: retired upstream (archive.canonical.com)"

SOURCES_FILE = "/etc/apt/sources.list"
SOURCES_DIR = "/etc/apt/sources.list.d"

SOURCE_SUFFIXES = (".list", ".sources")


def source_uri(line: str) -> str:
    """Return the URI of an active one-line source entry, or an empty string.

    Commented lines, blank lines, options blocks (``[arch=amd64]``) and any
    other directive are reported as "no URI" so that only real entries are
    rewritten.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return ""
    tokens = stripped.split()
    if tokens[0] not in ("deb", "deb-src"):
        return ""
    in_options = False
    for token in tokens[1:]:
        if in_options:
            in_options = not token.endswith("]")
            continue
        if token.startswith("["):
            in_options = not token.endswith("]")
            continue
        return token
    return ""


def host_of(uri: str) -> str:
    """Return the lower-case host name of a URI."""
    return (urlparse(uri).hostname or "").lower()


def is_retired_uri(uri: str) -> bool:
    """Return True when the URI points at a retired archive host."""
    return host_of(uri) in RETIRED_HOSTS


def clean_classic_sources(text: str) -> tuple[str, int]:
    """Comment out retired one-line source entries.

    Returns the new content and the number of entries disabled.
    """
    result = []
    disabled = 0
    for line in text.split("\n"):
        uri = source_uri(line)
        if uri and is_retired_uri(uri):
            result.append(MARKER)
            result.append(f"# {line.strip()}")
            disabled += 1
        else:
            result.append(line)
    return "\n".join(result), disabled


def _stanza_uris(lines: list[str]) -> list[str]:
    """Return every URI listed by a deb822 stanza, continuations included."""
    uris = []
    index = 0
    while index < len(lines):
        line = lines[index]
        key, separator, value = line.partition(":")
        if separator and key.strip().lower() == "uris":
            uris.extend(value.split())
            index += 1
            while index < len(lines) and lines[index][:1] in (" ", "\t"):
                uris.extend(lines[index].split())
                index += 1
            continue
        index += 1
    return uris


def _stanza_is_retired(lines: list[str]) -> bool:
    """Return True when a deb822 stanza references a retired host."""
    return any(is_retired_uri(uri) for uri in _stanza_uris(lines))


def _disable_stanza(lines: list[str]) -> tuple[list[str], bool]:
    """Add or fix ``Enabled: no`` in a stanza that references a retired host."""
    if not _stanza_is_retired(lines):
        return lines, False

    result = []
    disabled = False
    uris_line = -1
    for line in lines:
        key, separator, value = line.partition(":")
        field = key.strip().lower() if separator else ""
        if field == "enabled":
            if value.strip().lower() == "no":
                # already disabled, keep the file byte-identical
                return lines, False
            result.append("Enabled: no")
            disabled = True
            continue
        if field == "uris":
            uris_line = len(result)
        result.append(line)

    if not disabled:
        insert_at = uris_line + 1
        while insert_at < len(result) and result[insert_at][:1] in (" ", "\t"):
            insert_at += 1
        result.insert(insert_at, "Enabled: no")
    return result, True


def clean_deb822_sources(text: str) -> tuple[str, int]:
    """Disable retired deb822 stanzas.

    Returns the new content and the number of stanzas disabled.
    """
    result = []
    stanza = []
    disabled = 0
    for line in text.split("\n") + [""]:
        if line.strip():
            stanza.append(line)
            continue
        if stanza:
            cleaned, changed = _disable_stanza(stanza)
            result.extend(cleaned)
            disabled += int(changed)
            stanza = []
        result.append(line)
    # the sentinel above appends one separator that the text does not have
    if result and text.endswith("\n"):
        result.pop()
    return "\n".join(result), disabled


def clean_source_file(path: str, text: str) -> tuple[str, int]:
    """Clean a source file, choosing the parser from its extension."""
    if path.endswith(".sources"):
        return clean_deb822_sources(text)
    return clean_classic_sources(text)


def source_paths(device: LabDevice) -> list[str]:
    """Return the APT source files of the device that APT actually reads."""
    paths = [SOURCES_FILE]
    listing = device.run(["ls", "-1", SOURCES_DIR], hide=True)
    if listing.failed:
        return paths
    for name in listing.stdout.split():
        if name.endswith(SOURCE_SUFFIXES):
            paths.append(f"{SOURCES_DIR}/{name}")
    return paths


def main():
    parser = ArgumentParser(description="Disable APT sources that are retired upstream")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would change instead of writing the files",
    )
    args = parser.parse_args()

    try:
        device = LabDevice()
    except RuntimeError as error:
        print(f"ERROR: {error}")
        sys.exit(1)

    disabled = 0
    for path in source_paths(device):
        current = device.run(["cat", path], hide=True)
        if current.failed:
            print(
                f"SKIP: cannot read {path} on {device.host} "
                f"(exit code: {current.exited})"
            )
            continue

        cleaned, changed = clean_source_file(path, current.stdout)
        if not changed:
            continue

        disabled += changed
        if args.dry_run:
            print(f"Would disable {changed} retired source(s) in {path}")
            continue

        written = device.write_remote_file(path, cleaned)
        if written.failed:
            print(
                f"ERROR: failed to write {path} on {device.host} "
                f"(exit code: {written.exited})"
            )
            continue
        print(f"Disabled {changed} retired source(s) in {path}")

    if not disabled:
        print(f"No retired APT sources found on {device.host}.")


if __name__ == "__main__":
    main()
