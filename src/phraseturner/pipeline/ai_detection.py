"""Stage 2 analyzer: AI detection.

Wraps ``is-it-slop`` v0.5.0 in ``asyncio.to_thread()`` for the
ensemble path (Tier >= 2), with a stylometric-only fallback using
burstiness, hapax ratio, and Zipf R² when the detector is unavailable
(Tier < 2).

This module is called concurrently with Stage 1 via
``asyncio.gather`` in the pipeline orchestrator (Task 3.10).

Implements §4.4.
Requirements: FR-PIPELINE-07.
"""

from __future__ import annotations

import asyncio
import dataclasses
from typing import Any

import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Thresholds — FR-PIPELINE-07.2
# ---------------------------------------------------------------------------

_AI_THRESHOLD: float = 0.7
"""Probability at or above which text is classified ``likely-ai``."""

_HUMAN_THRESHOLD: float = 0.3
"""Probability at or below which text is classified ``likely-human``."""

# Stylometric heuristic thresholds (calibrated from research)
_STYLO_BURSTINESS_LOW: float = 0.20
_STYLO_BURSTINESS_HIGH: float = 0.35
_STYLO_HAPAX_LOW: float = 0.35
_STYLO_HAPAX_HIGH: float = 0.45
_STYLO_ZIPF_HIGH: float = 0.96

# Stylometric signal weights for probability estimation
_WEIGHT_BURSTINESS: float = 0.4
_WEIGHT_HAPAX: float = 0.3
_WEIGHT_ZIPF: float = 0.3


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class AIDetectionResult:
    """Result of the AI detection stage.

    Attributes:
        classification: One of ``likely-ai``, ``likely-human``, or
            ``uncertain``.  Implements AC-FR-PIPELINE-07.2.
        ai_probability: Estimated probability that the text is
            AI-generated (0.0-1.0).
        detection_method: ``ensemble`` when ``is-it-slop`` was used,
            ``stylometric`` when falling back to heuristic signals.
            Implements AC-FR-PIPELINE-07.4.
        stylometric_signals: Burstiness, hapax ratio, and Zipf R²
            values when using the stylometric fallback; ``None`` for
            the ensemble path.
    """

    classification: str
    ai_probability: float
    detection_method: str
    stylometric_signals: dict[str, float] | None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _classify(probability: float) -> str:
    """Map a probability to a classification label.

    Implements AC-FR-PIPELINE-07.2.
    """
    if probability >= _AI_THRESHOLD:
        return "likely-ai"
    if probability <= _HUMAN_THRESHOLD:
        return "likely-human"
    return "uncertain"


def _estimate_stylometric_probability(
    burstiness: float,
    hapax_ratio: float,
    zipf_r_squared: float,
) -> float:
    """Estimate AI probability from stylometric signals.

    Low burstiness, low hapax ratio, and high Zipf R² all indicate
    AI-generated text.  Each signal is mapped to a 0-1 "AI-ness"
    score and combined via a weighted average.

    Returns:
        A float in [0.0, 1.0].
    """
    # Burstiness: lower → more AI-like.  Map [0, 1] → [1, 0].
    burst_signal = max(0.0, min(1.0, 1.0 - burstiness))

    # Hapax ratio: lower → more AI-like.  Map [0, 1] → [1, 0].
    hapax_signal = max(0.0, min(1.0, 1.0 - hapax_ratio))

    # Zipf R²: higher → more AI-like.  Already in [0, 1].
    zipf_signal = max(0.0, min(1.0, zipf_r_squared))

    return (
        _WEIGHT_BURSTINESS * burst_signal
        + _WEIGHT_HAPAX * hapax_signal
        + _WEIGHT_ZIPF * zipf_signal
    )


def _run_stylometric_fallback(
    naturalness_result: Any | None,
) -> AIDetectionResult:
    """Classify using stylometric heuristics only.

    Implements AC-FR-PIPELINE-07.4.
    """
    if naturalness_result is None:
        return AIDetectionResult(
            classification="uncertain",
            ai_probability=0.5,
            detection_method="stylometric",
            stylometric_signals=None,
        )

    burstiness: float = getattr(naturalness_result, "burstiness", 0.5)
    hapax_ratio: float = getattr(naturalness_result, "hapax_ratio", 0.5)
    zipf_r_squared: float = getattr(naturalness_result, "zipf_r_squared", 0.5)

    signals: dict[str, float] = {
        "burstiness": burstiness,
        "hapax_ratio": hapax_ratio,
        "zipf_r_squared": zipf_r_squared,
    }

    # Heuristic classification
    if (
        burstiness < _STYLO_BURSTINESS_LOW
        and hapax_ratio < _STYLO_HAPAX_LOW
        and zipf_r_squared > _STYLO_ZIPF_HIGH
    ):
        classification = "likely-ai"
    elif burstiness > _STYLO_BURSTINESS_HIGH and hapax_ratio > _STYLO_HAPAX_HIGH:
        classification = "likely-human"
    else:
        classification = "uncertain"

    ai_probability = _estimate_stylometric_probability(burstiness, hapax_ratio, zipf_r_squared)

    return AIDetectionResult(
        classification=classification,
        ai_probability=ai_probability,
        detection_method="stylometric",
        stylometric_signals=signals,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def run_ai_detection(
    text: str,
    slop_detector: Any | None,
    naturalness_result: Any | None,
) -> AIDetectionResult:
    """Run AI detection on *text*. Implements FR-PIPELINE-07.

    Uses the ``is-it-slop`` ensemble detector when available (Tier >= 2),
    falling back to stylometric heuristics otherwise.

    Args:
        text: The full input text to analyse.
        slop_detector: An ``is-it-slop`` detector instance, or ``None``
            when the library is unavailable (Tier < 2).
        naturalness_result: A :class:`NaturalnessResult` from Stage 1,
            used for the stylometric fallback path.  May be ``None``
            if Stage 1 has not completed or failed.

    Returns:
        An :class:`AIDetectionResult` with classification, probability,
        detection method, and optional stylometric signals.
    """
    # Ensemble path — AC-FR-PIPELINE-07.1, AC-FR-PIPELINE-07.3
    if slop_detector is not None:
        try:
            score: float = await asyncio.to_thread(slop_detector.score, text)
            return AIDetectionResult(
                classification=_classify(score),
                ai_probability=score,
                detection_method="ensemble",
                stylometric_signals=None,
            )
        except Exception:
            logger.warning(
                "slop_detector_failed",
                msg="is-it-slop raised an exception — falling back to stylometric",
            )
            # Fall through to stylometric fallback

    # Stylometric fallback — AC-FR-PIPELINE-07.4
    return _run_stylometric_fallback(naturalness_result)
