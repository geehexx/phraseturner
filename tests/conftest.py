"""Shared pytest fixtures for phraseturner tests."""

from __future__ import annotations

import pytest


@pytest.fixture()
def sample_text() -> str:
    """Return a short sample text for testing."""
    return (
        "The quick brown fox jumps over the lazy dog. "
        "This sentence provides additional context for analysis."
    )
