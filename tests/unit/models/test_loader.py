"""Unit tests for ModelLoader.

Tests tier detection, availability flags, config-based skipping,
cleanup, and model version reporting.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from phraseturner.config import ServerConfig
from phraseturner.models.loader import ModelLoader

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config() -> ServerConfig:
    """Return a ServerConfig with all optional models disabled for fast tests."""
    return ServerConfig(
        disable_t5=True,
        disable_slop=True,
        disable_embed=True,
    )


@pytest.fixture
def loader(config: ServerConfig) -> ModelLoader:
    """Return a fresh ModelLoader with all models disabled."""
    return ModelLoader(config)


# ---------------------------------------------------------------------------
# Tier detection
# ---------------------------------------------------------------------------


class TestOperatingTier:
    """Tests for operating_tier property. Implements §1.2."""

    def test_tier_0_no_models(self, loader: ModelLoader) -> None:
        """Tier 0 when no models are loaded."""
        assert loader.operating_tier == 0

    def test_tier_1_spacy_only(self, loader: ModelLoader) -> None:
        """Tier 1 when only spaCy is loaded."""
        loader._nlp = MagicMock()
        assert loader.operating_tier == 1

    def test_tier_2_spacy_and_slop(self, loader: ModelLoader) -> None:
        """Tier 2 when spaCy + is-it-slop are loaded."""
        loader._nlp = MagicMock()
        loader._slop_detector = MagicMock()
        assert loader.operating_tier == 2

    def test_tier_3_spacy_slop_t5(self, loader: ModelLoader) -> None:
        """Tier 3 when spaCy + is-it-slop + T5 are loaded."""
        loader._nlp = MagicMock()
        loader._slop_detector = MagicMock()
        loader._t5_session = MagicMock()
        loader._t5_tokenizer = MagicMock()
        assert loader.operating_tier == 3

    def test_tier_4_all_models(self, loader: ModelLoader) -> None:
        """Tier 4 when all models are loaded."""
        loader._nlp = MagicMock()
        loader._slop_detector = MagicMock()
        loader._t5_session = MagicMock()
        loader._t5_tokenizer = MagicMock()
        loader._fastembed = MagicMock()
        assert loader.operating_tier == 4

    def test_tier_2_without_t5_tokenizer(self, loader: ModelLoader) -> None:
        """Tier 2 when T5 session exists but tokenizer is missing."""
        loader._nlp = MagicMock()
        loader._slop_detector = MagicMock()
        loader._t5_session = MagicMock()
        # No tokenizer — t5_available is False
        assert loader.operating_tier == 2


# ---------------------------------------------------------------------------
# Availability flags
# ---------------------------------------------------------------------------


class TestAvailabilityFlags:
    """Tests for *_available properties."""

    def test_all_unavailable_initially(self, loader: ModelLoader) -> None:
        assert not loader.spacy_available
        assert not loader.fastembed_available
        assert not loader.slop_available
        assert not loader.t5_available

    def test_spacy_available_when_set(self, loader: ModelLoader) -> None:
        loader._nlp = MagicMock()
        assert loader.spacy_available

    def test_t5_requires_both_session_and_tokenizer(self, loader: ModelLoader) -> None:
        loader._t5_session = MagicMock()
        assert not loader.t5_available
        loader._t5_tokenizer = MagicMock()
        assert loader.t5_available


# ---------------------------------------------------------------------------
# Config-based skipping
# ---------------------------------------------------------------------------


class TestConfigSkipping:
    """Tests that disabled models are skipped during loading."""

    @pytest.mark.asyncio
    async def test_load_fastembed_skipped_when_disabled(self, loader: ModelLoader) -> None:
        await loader.load_fastembed()
        assert not loader.fastembed_available

    @pytest.mark.asyncio
    async def test_load_slop_skipped_when_disabled(self, loader: ModelLoader) -> None:
        await loader.load_slop_detector()
        assert not loader.slop_available

    @pytest.mark.asyncio
    async def test_load_t5_skipped_when_disabled(self, loader: ModelLoader) -> None:
        await loader.load_t5()
        assert not loader.t5_available


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


class TestCleanup:
    """Tests for cleanup() method."""

    @pytest.mark.asyncio
    async def test_cleanup_releases_all_models(self, loader: ModelLoader) -> None:
        loader._nlp = MagicMock()
        loader._fastembed = MagicMock()
        loader._slop_detector = MagicMock()
        loader._t5_session = MagicMock()
        loader._t5_tokenizer = MagicMock()

        await loader.cleanup()

        assert loader.nlp is None
        assert loader.fastembed is None
        assert loader.slop_detector is None
        assert loader.t5_session is None
        assert loader.t5_tokenizer is None
        assert loader.operating_tier == 0


# ---------------------------------------------------------------------------
# Model versions
# ---------------------------------------------------------------------------


class TestModelVersions:
    """Tests for model_versions property."""

    def test_empty_when_no_models(self, loader: ModelLoader) -> None:
        assert loader.model_versions == {}

    def test_includes_spacy_version(self, loader: ModelLoader) -> None:
        mock_nlp = MagicMock()
        mock_nlp.meta = {"version": "3.8.4"}
        loader._nlp = mock_nlp
        versions = loader.model_versions
        assert versions["spacy"] == "3.8.4"

    def test_includes_t5_version(self, loader: ModelLoader) -> None:
        loader._t5_session = MagicMock()
        versions = loader.model_versions
        assert versions["t5"] == "flan-t5-base-int8"

    def test_includes_fastembed_model_name(self, loader: ModelLoader) -> None:
        loader._fastembed = MagicMock()
        versions = loader.model_versions
        assert versions["fastembed"] == loader._config.embed_model

    def test_includes_slop_version(self, loader: ModelLoader) -> None:
        loader._slop_detector = MagicMock()
        versions = loader.model_versions
        assert versions["is_it_slop"] == "0.5.0"


# ---------------------------------------------------------------------------
# Warmup
# ---------------------------------------------------------------------------


class TestWarmup:
    """Tests for warmup_t5() method."""

    @pytest.mark.asyncio
    async def test_warmup_noop_when_t5_unavailable(self, loader: ModelLoader) -> None:
        """warmup_t5 should be a no-op when T5 is not loaded."""
        # Should not raise
        await loader.warmup_t5()

    @pytest.mark.asyncio
    async def test_warmup_handles_error_gracefully(self, loader: ModelLoader) -> None:
        """warmup_t5 should log warning on error, not raise."""
        loader._t5_session = MagicMock()
        loader._t5_tokenizer = MagicMock(side_effect=TypeError("mock error"))

        # Should not raise — errors are caught and logged
        await loader.warmup_t5()


# ---------------------------------------------------------------------------
# Coverage: optional model loading success/failure paths
# ---------------------------------------------------------------------------


class TestLoaderFastembedSuccess:
    """ModelLoader.load_fastembed() success and failure paths."""

    async def test_load_fastembed_success(self) -> None:
        """load_fastembed stores the model when loading succeeds."""
        from unittest.mock import MagicMock, patch

        config = ServerConfig(disable_embed=False, disable_t5=True, disable_slop=True)
        loader = ModelLoader(config)
        mock_model = MagicMock()
        with patch("phraseturner.models.loader.asyncio.to_thread", return_value=mock_model):
            await loader.load_fastembed()
        assert loader.fastembed_available
        assert loader.fastembed is mock_model

    async def test_load_fastembed_failure_graceful(self) -> None:
        """load_fastembed logs warning on failure, does not raise."""
        from unittest.mock import patch

        config = ServerConfig(disable_embed=False, disable_t5=True, disable_slop=True)
        loader = ModelLoader(config)
        with patch(
            "phraseturner.models.loader.asyncio.to_thread",
            side_effect=ImportError("fastembed not installed"),
        ):
            await loader.load_fastembed()
        assert not loader.fastembed_available


class TestLoaderSlopSuccess:
    """ModelLoader.load_slop_detector() success and failure paths."""

    async def test_load_slop_detector_success(self) -> None:
        """load_slop_detector stores the wrapper when loading succeeds."""
        from unittest.mock import MagicMock, patch

        config = ServerConfig(disable_slop=False, disable_t5=True, disable_embed=True)
        loader = ModelLoader(config)
        mock_wrapper = MagicMock()
        with patch("phraseturner.models.loader.asyncio.to_thread", return_value=mock_wrapper):
            await loader.load_slop_detector()
        assert loader.slop_available
        assert loader.slop_detector is mock_wrapper

    async def test_load_slop_detector_failure_graceful(self) -> None:
        """load_slop_detector logs warning on failure, does not raise."""
        from unittest.mock import patch

        config = ServerConfig(disable_slop=False, disable_t5=True, disable_embed=True)
        loader = ModelLoader(config)
        with patch(
            "phraseturner.models.loader.asyncio.to_thread",
            side_effect=ImportError("is_it_slop not installed"),
        ):
            await loader.load_slop_detector()
        assert not loader.slop_available


class TestLoaderT5:
    """ModelLoader.load_t5() success and failure paths."""

    async def test_load_t5_success(self) -> None:
        """load_t5 stores session and tokenizer when loading succeeds."""
        from unittest.mock import MagicMock, patch

        config = ServerConfig(disable_t5=False, disable_slop=True, disable_embed=True)
        loader = ModelLoader(config)
        mock_sessions = (MagicMock(), MagicMock())
        mock_tokenizer = MagicMock()
        with patch(
            "phraseturner.models.loader.asyncio.to_thread",
            return_value=(mock_sessions, mock_tokenizer),
        ):
            await loader.load_t5()
        assert loader.t5_available
        assert loader.t5_session is mock_sessions
        assert loader.t5_tokenizer is mock_tokenizer

    async def test_load_t5_failure_graceful(self) -> None:
        """load_t5 logs warning on failure, does not raise."""
        from unittest.mock import patch

        config = ServerConfig(disable_t5=False, disable_slop=True, disable_embed=True)
        loader = ModelLoader(config)
        with patch(
            "phraseturner.models.loader.asyncio.to_thread",
            side_effect=FileNotFoundError("model not found"),
        ):
            await loader.load_t5()
        assert not loader.t5_available


class TestLoaderWarmupSuccess:
    """ModelLoader.warmup_t5() success path."""

    async def test_warmup_t5_success(self) -> None:
        """warmup_t5 completes without error when T5 is available."""
        from unittest.mock import MagicMock, patch

        config = ServerConfig(disable_t5=True, disable_slop=True, disable_embed=True)
        loader = ModelLoader(config)
        loader._t5_session = (MagicMock(), MagicMock())
        loader._t5_tokenizer = MagicMock()
        with patch("phraseturner.models.loader.asyncio.to_thread", return_value=None):
            await loader.warmup_t5()
        # No exception means success
