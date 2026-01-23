"""Shared device utilities for testing."""

from toolbox.devices import Device


class TrivialDevice(Device):
    """Trivial device class for testing purposes.

    This is a minimal Device implementation that can be used in tests.
    The run() method should be mocked in tests as needed.
    """

    def __init__(self, interfaces=None):
        super().__init__("test-host", interfaces=interfaces)

    def run(self, command, **kwargs):
        """Minimal run implementation that will be mocked in tests."""
        pass
