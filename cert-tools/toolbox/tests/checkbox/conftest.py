"""Fixtures for checkbox helpers tests."""

import sys
from unittest.mock import MagicMock

# Mock snapstore module before any test imports
sys.modules["snapstore"] = MagicMock()
sys.modules["snapstore.client"] = MagicMock()
sys.modules["snapstore.info"] = MagicMock()
