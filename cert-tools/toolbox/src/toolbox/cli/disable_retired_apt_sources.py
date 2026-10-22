"""Comment out apt sources whose archive no longer exists upstream.

The focal OEM images ship ``deb http://archive.canonical.com/ubuntu focal
partner``. That archive is retired, so ``apt-get update`` fails on it and the
job stops before the tests. This CLI comments the entry out on the device.
"""

from toolbox.devices.lab import LabDevice

#: Hosts that no longer serve their archives.
RETIRED_HOSTS = ("archive.canonical.com",)

SOURCES = "/etc/apt/sources.list"
SOURCES_DIR = "/etc/apt/sources.list.d"
MARKER = "# disabled: retired upstream: "


def is_retired(line: str, hosts=RETIRED_HOSTS) -> bool:
    """Return True for an active source entry that points at a retired host."""
    entry = line.strip()
    if not entry.startswith(("deb ", "deb-src ")):
        return False
    return any(f"://{host}/" in entry for host in hosts)


def comment_out(text: str, hosts=RETIRED_HOSTS) -> tuple[str, int]:
    """Return the text with retired entries commented out, and how many were."""
    lines = text.splitlines()
    cleaned = [
        MARKER + line.strip() if is_retired(line, hosts) else line for line in lines
    ]
    return "\n".join(cleaned) + "\n", sum(a != b for a, b in zip(lines, cleaned))


def source_files(device: LabDevice) -> list[str]:
    """Return the apt source files of the device."""
    paths = [SOURCES]
    listing = device.run(["ls", "-1", SOURCES_DIR], hide=True)
    if not listing.failed:
        paths += [
            f"{SOURCES_DIR}/{name}"
            for name in listing.stdout.split()
            if name.endswith(".list")
        ]
    return paths


def main():
    device = LabDevice()
    disabled = 0
    for path in source_files(device):
        current = device.run(["cat", path], hide=True)
        if current.failed:
            continue
        cleaned, changed = comment_out(current.stdout)
        if changed:
            device.write_remote_file(path, cleaned)
            disabled += changed
            print(f"{path}: commented out {changed} retired source(s)")
    print(f"{device.host}: {disabled} retired source(s) disabled")
