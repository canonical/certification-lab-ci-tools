import sys
from collections import Counter

import pytest

from toolbox.cli import ensure_stable_snaps
from toolbox.interfaces.snaps import SnapInstallError, SnapSpec


@pytest.fixture
def snap_interface(mocker):
    mocker.patch.object(sys, "argv", ["ensure-stable-snaps"])
    mock_lab = mocker.patch.object(ensure_stable_snaps, "LabDevice")
    interface = mock_lab.return_value.interfaces.__getitem__.return_value
    return interface


class TestEnsureStableSnaps:
    """Tests for the ensure_stable_snaps.main() entry point."""

    def test_all_snaps_refresh_first_try(self, snap_interface):
        """All snaps refresh on the first attempt, so main() exits cleanly."""
        snaps = [
            SnapSpec("checkbox22", "latest", "beta", None),
            SnapSpec("core", "latest", "stable", None),
            SnapSpec("core22", "latest", "stable", None),
        ]
        snap_interface.list.return_value = snaps

        ensure_stable_snaps.main()

        assert snap_interface.install.call_count == len(snaps)
        for snap in snaps:
            assert snap.risk == "stable"

    def test_two_snaps_refresh_on_retry(self, snap_interface):
        """Two snaps fail on the first try but succeed when retried."""
        snaps = [
            SnapSpec("checkbox22", "latest", "stable", None),
            SnapSpec("core", "latest", "stable", None),
            SnapSpec("core22", "latest", "stable", None),
        ]
        snap_interface.list.return_value = snaps
        failing_first = {"checkbox22", "core22"}
        attempts = Counter()

        def install(name, channel, **kwargs):
            attempts[name] += 1
            if name in failing_first and attempts[name] == 1:
                raise SnapInstallError(f"{name} failed to refresh")

        snap_interface.install.side_effect = install

        ensure_stable_snaps.main()

        assert attempts == Counter({"checkbox22": 2, "core22": 2, "core": 1})

    def test_one_snap_never_refreshes_raises_systemexit(self, snap_interface):
        """A snap that never refreshes exhausts retries and raises SystemExit."""
        snaps = [
            SnapSpec("checkbox22", "latest", "stable", None),
            SnapSpec("core", "latest", "stable", None),
        ]
        snap_interface.list.return_value = snaps
        attempts = Counter()

        def install(name, channel, **kwargs):
            attempts[name] += 1
            if name == "checkbox22":
                raise SnapInstallError("checkbox22 failed to refresh")

        snap_interface.install.side_effect = install

        with pytest.raises(SystemExit) as exc_info:
            ensure_stable_snaps.main()

        assert "checkbox22" in str(exc_info.value)
        assert attempts["checkbox22"] == ensure_stable_snaps.MAX_RETRY + 1
