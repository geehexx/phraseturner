"""Tests for the AI detection stage (Stage 2).

Covers the ensemble path (is-it-slop), stylometric fallback,
classification thresholds, and error handling.

Requirements: FR-PIPELINE-07.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from phraseturner.pipeline.ai_detection import (
    _classify,
    _estimate_stylometric_probability,
    _run_stylometric_fallback,
    run_ai_detection,
)
from phraseturner.pipeline.naturalness import NaturalnessResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_naturalness(
    burstiness: float = 0.5,
    hapax_ratio: float = 0.5,
    zipf_r_squared: float = 0.5,
) -> NaturalnessResult:
    """Create a NaturalnessResult with specified signals."""
    return NaturalnessResult(
        burstiness=burstiness,
        length_skewness=0.0,
        hapax_ratio=hapax_ratio,
        zipf_r_squared=zipf_r_squared,
        punctuation_entropy=0.0,
        starter_diversity=0.0,
    )


# ---------------------------------------------------------------------------
# _classify tests
# ---------------------------------------------------------------------------


class TestClassify:
    """Tests for the _classify helper."""

    def test_likely_ai_at_threshold(self) -> None:
        assert _classify(0.7) == "likely-ai"

    def test_likely_ai_above_threshold(self) -> None:
        assert _classify(0.95) == "likely-ai"

    def test_likely_human_at_threshold(self) -> None:
        assert _classify(0.3) == "likely-human"

    def test_likely_human_below_threshold(self) -> None:
        assert _classify(0.1) == "likely-human"

    def test_uncertain_between_thresholds(self) -> None:
        assert _classify(0.5) == "uncertain"

    def test_uncertain_just_above_human(self) -> None:
        assert _classify(0.31) == "uncertain"

    def test_uncertain_just_below_ai(self) -> None:
        assert _classify(0.69) == "uncertain"


# ---------------------------------------------------------------------------
# _estimate_stylometric_probability tests
# ---------------------------------------------------------------------------


class TestEstimateStylometricProbability:
    """Tests for the weighted probability estimator."""

    def test_all_ai_signals(self) -> None:
        """Low burstiness, low hapax, high Zipf -> high probability."""
        prob = _estimate_stylometric_probability(0.0, 0.0, 1.0)
        assert prob == pytest.approx(1.0)

    def test_all_human_signals(self) -> None:
        """High burstiness, high hapax, low Zipf -> low probability."""
        prob = _estimate_stylometric_probability(1.0, 1.0, 0.0)
        assert prob == pytest.approx(0.0)

    def test_mixed_signals(self) -> None:
        """Middle-of-the-road signals -> ~0.5."""
        prob = _estimate_stylometric_probability(0.5, 0.5, 0.5)
        assert prob == pytest.approx(0.5)

    def test_result_clamped_to_unit_range(self) -> None:
        """Even with extreme inputs, result stays in [0, 1]."""
        prob = _estimate_stylometric_probability(-1.0, -1.0, 2.0)
        assert 0.0 <= prob <= 1.0


# ---------------------------------------------------------------------------
# _run_stylometric_fallback tests
# ---------------------------------------------------------------------------


class TestStylometricFallback:
    """Tests for the stylometric fallback path."""

    def test_none_naturalness_returns_uncertain(self) -> None:
        result = _run_stylometric_fallback(None)
        assert result.classification == "uncertain"
        assert result.ai_probability == 0.5
        assert result.detection_method == "stylometric"
        assert result.stylometric_signals is None

    def test_ai_like_signals(self) -> None:
        """Low burstiness + low hapax + high Zipf -> likely-ai."""
        nat = _make_naturalness(burstiness=0.1, hapax_ratio=0.2, zipf_r_squared=0.98)
        result = _run_stylometric_fallback(nat)
        assert result.classification == "likely-ai"
        assert result.detection_method == "stylometric"
        assert result.stylometric_signals is not None
        assert result.stylometric_signals["burstiness"] == 0.1

    def test_human_like_signals(self) -> None:
        """High burstiness + high hapax -> likely-human."""
        nat = _make_naturalness(burstiness=0.8, hapax_ratio=0.7, zipf_r_squared=0.5)
        result = _run_stylometric_fallback(nat)
        assert result.classification == "likely-human"
        assert result.detection_method == "stylometric"

    def test_uncertain_signals(self) -> None:
        """Middle signals -> uncertain (between calibrated thresholds)."""
        # burstiness 0.25 is between AI-typical (<0.20) and human-typical (>0.35)
        # hapax 0.40 is between AI-typical (<0.35) and human-typical (>0.45)
        nat = _make_naturalness(burstiness=0.25, hapax_ratio=0.40, zipf_r_squared=0.5)
        result = _run_stylometric_fallback(nat)
        assert result.classification == "uncertain"
        assert result.detection_method == "stylometric"
        assert result.stylometric_signals is not None


# ---------------------------------------------------------------------------
# run_ai_detection tests (async)
# ---------------------------------------------------------------------------


class TestRunAIDetection:
    """Tests for the main async entry point."""

    @pytest.mark.asyncio
    async def test_ensemble_path_likely_ai(self) -> None:
        """Detector returning 0.85 -> likely-ai via ensemble."""
        detector = MagicMock()
        detector.score.return_value = 0.85

        result = await run_ai_detection("some text", detector, None)

        assert result.classification == "likely-ai"
        assert result.ai_probability == 0.85
        assert result.detection_method == "ensemble"
        assert result.stylometric_signals is None
        detector.score.assert_called_once_with("some text")

    @pytest.mark.asyncio
    async def test_ensemble_path_likely_human(self) -> None:
        """Detector returning 0.15 -> likely-human via ensemble."""
        detector = MagicMock()
        detector.score.return_value = 0.15

        result = await run_ai_detection("human text", detector, None)

        assert result.classification == "likely-human"
        assert result.ai_probability == 0.15
        assert result.detection_method == "ensemble"

    @pytest.mark.asyncio
    async def test_ensemble_path_uncertain(self) -> None:
        """Detector returning 0.5 -> uncertain via ensemble."""
        detector = MagicMock()
        detector.score.return_value = 0.5

        result = await run_ai_detection("ambiguous text", detector, None)

        assert result.classification == "uncertain"
        assert result.detection_method == "ensemble"

    @pytest.mark.asyncio
    async def test_fallback_when_no_detector(self) -> None:
        """No detector -> stylometric fallback."""
        nat = _make_naturalness(burstiness=0.5, hapax_ratio=0.5, zipf_r_squared=0.5)
        result = await run_ai_detection("some text", None, nat)

        assert result.detection_method == "stylometric"
        assert result.stylometric_signals is not None

    @pytest.mark.asyncio
    async def test_fallback_when_detector_raises(self) -> None:
        """Detector exception -> graceful fallback to stylometric."""
        detector = MagicMock()
        detector.score.side_effect = RuntimeError("model crashed")

        nat = _make_naturalness(burstiness=0.5, hapax_ratio=0.5, zipf_r_squared=0.5)
        result = await run_ai_detection("some text", detector, nat)

        assert result.detection_method == "stylometric"
        assert result.stylometric_signals is not None

    @pytest.mark.asyncio
    async def test_fallback_no_detector_no_naturalness(self) -> None:
        """No detector and no naturalness -> uncertain with 0.5."""
        result = await run_ai_detection("some text", None, None)

        assert result.classification == "uncertain"
        assert result.ai_probability == 0.5
        assert result.detection_method == "stylometric"
        assert result.stylometric_signals is None
