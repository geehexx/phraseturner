"""Tests for phraseturner.models.download — model download on first run.

Validates: NFR-DIST-04 (AC-NFR-DIST-04.1 through AC-NFR-DIST-04.4).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from phraseturner.models.download import (
    _T5_REQUIRED_FILES,
    ensure_all_models,
    ensure_spacy_model,
    ensure_t5_model,
)

# ---------------------------------------------------------------------------
# ensure_spacy_model
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ensure_spacy_model_already_installed() -> None:
    """Skip download when spaCy model is already installed."""
    with patch("spacy.util.is_package", return_value=True) as mock_check:
        await ensure_spacy_model("en_core_web_sm")
        mock_check.assert_called_once_with("en_core_web_sm")


@pytest.mark.asyncio
async def test_ensure_spacy_model_downloads_when_missing() -> None:
    """Download spaCy model when not installed."""
    with (
        patch("spacy.util.is_package", return_value=False),
        patch("spacy.cli.download") as mock_download,
    ):
        await ensure_spacy_model("en_core_web_sm")
        mock_download.assert_called_once_with("en_core_web_sm")


# ---------------------------------------------------------------------------
# ensure_t5_model
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ensure_t5_model_skips_when_cached(tmp_path: Path) -> None:
    """Skip download when all required T5 files are present."""
    for fname in _T5_REQUIRED_FILES:
        (tmp_path / fname).write_text("dummy")

    result = await ensure_t5_model(tmp_path)
    assert result == tmp_path


@pytest.mark.asyncio
async def test_ensure_t5_model_downloads_when_missing(tmp_path: Path) -> None:
    """Download T5 model when files are missing."""

    def fake_snapshot_download(**kwargs: Any) -> str:
        local_dir = Path(kwargs["local_dir"])
        for fname in _T5_REQUIRED_FILES:
            (local_dir / fname).write_text("dummy-model-data")
        return str(local_dir)

    with patch(
        "huggingface_hub.snapshot_download",
        side_effect=fake_snapshot_download,
    ):
        result = await ensure_t5_model(tmp_path)
        assert result == tmp_path
        for fname in _T5_REQUIRED_FILES:
            assert (tmp_path / fname).exists()


@pytest.mark.asyncio
async def test_ensure_t5_model_creates_directory(tmp_path: Path) -> None:
    """Create model directory if it does not exist."""
    model_dir = tmp_path / "nested" / "models"

    def fake_snapshot_download(**kwargs: Any) -> str:
        local_dir = Path(kwargs["local_dir"])
        for fname in _T5_REQUIRED_FILES:
            (local_dir / fname).write_text("dummy")
        return str(local_dir)

    with patch(
        "huggingface_hub.snapshot_download",
        side_effect=fake_snapshot_download,
    ):
        result = await ensure_t5_model(model_dir)
        assert result == model_dir
        assert model_dir.is_dir()


@pytest.mark.asyncio
async def test_ensure_t5_model_raises_on_incomplete_download(tmp_path: Path) -> None:
    """Raise FileNotFoundError when download is incomplete."""

    def fake_snapshot_download(**kwargs: Any) -> str:
        # Only create some files — simulate incomplete download
        local_dir = Path(kwargs["local_dir"])
        (local_dir / "config.json").write_text("{}")
        return str(local_dir)

    with (
        patch(
            "huggingface_hub.snapshot_download",
            side_effect=fake_snapshot_download,
        ),
        pytest.raises(FileNotFoundError, match="missing files"),
    ):
        await ensure_t5_model(tmp_path)


# ---------------------------------------------------------------------------
# ensure_all_models
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ensure_all_models_with_t5_disabled() -> None:
    """Skip T5 download when disable_t5 is True."""
    config = MagicMock()
    config.spacy_model = "en_core_web_sm"
    config.disable_t5 = True

    with patch("spacy.util.is_package", return_value=True):
        await ensure_all_models(config)


@pytest.mark.asyncio
async def test_ensure_all_models_downloads_both(tmp_path: Path) -> None:
    """Download both spaCy and T5 when neither is cached."""
    model_dir = tmp_path / "models"

    config = MagicMock()
    config.spacy_model = "en_core_web_sm"
    config.disable_t5 = False
    config.model_dir = model_dir

    def fake_snapshot_download(**kwargs: Any) -> str:
        local_dir = Path(kwargs["local_dir"])
        local_dir.mkdir(parents=True, exist_ok=True)
        for fname in _T5_REQUIRED_FILES:
            (local_dir / fname).write_text("dummy")
        return str(local_dir)

    with (
        patch("spacy.util.is_package", return_value=True),
        patch(
            "huggingface_hub.snapshot_download",
            side_effect=fake_snapshot_download,
        ),
    ):
        await ensure_all_models(config)
