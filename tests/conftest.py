"""Pytest fixtures shared across the suite."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _fast_ezo_delays(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make EZO command delays effectively zero during tests."""
    monkeypatch.setattr("reef_controller.sensors.ezo.time.sleep", lambda *_: None)
