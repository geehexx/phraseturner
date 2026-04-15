"""Stage 4: Score aggregation for the phraseturner analysis pipeline.

Computes a composite health score across 5 dimensions with configurable
weights, letter grades, status indicators, and focus mode support.

Implements FR-HEALTH-01, FR-HEALTH-02, FR-HEALTH-03, FR-HEALTH-04.
Design reference: §4.6.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from phraseturner.models.analysis import DimensionScore, HealthScore
from phraseturner.models.inputs import FocusMode

if TYPE_CHECKING:
    from phraseturner.personas.schema import HealthScoreWeights

# --- Constants ---

DIMENSIONS = (
    "readability",
    "naturalness",
    "vocabulary",
    "semantic_preservation",
    "tone_compliance",
)
"""Canonical ordering of the 5 health score dimensions."""

DEFAULT_WEIGHTS: dict[str, float] = {
    "readability": 0.25,
    "naturalness": 0.30,
    "vocabulary": 0.20,
    "semantic_preservation": 0.15,
    "tone_compliance": 0.10,
}
"""Default dimension weights. Implements AC-FR-HEALTH-01.1."""

# --- Gaussian readability scoring ---

CHANNEL_READABILITY_TARGETS: dict[str, tuple[float, float]] = {
    "slack-casual": (7.0, 2.0),
    "jira-ticket": (9.0, 2.0),
    "pr-review": (12.0, 3.0),
    "confluence-docs": (11.0, 2.0),
    "technical-docs": (14.0, 3.0),
    "email-professional": (10.0, 2.5),
    "blog-post": (8.0, 3.0),
    "executive-summary": (12.0, 2.0),
}
"""Channel-specific (target_grade, sigma) tuples for Gaussian readability scoring."""

_DEFAULT_TARGET_GRADE: float = 10.0
"""Default target grade when no persona/channel is specified."""

_DEFAULT_SIGMA: float = 4.0
"""Default sigma when no persona/channel is specified."""

_READABILITY_SCORE_FLOOR: float = 5.0
"""Minimum readability score to prevent single-dimension collapse in composite scoring.

Even text that is far from the target grade level should score at least 5/100
rather than near-zero. This preserves discriminative power while ensuring the
composite health score remains meaningful for extreme mismatches.
"""


def gaussian_readability_score(
    consensus_grade: float,
    target_grade: float = 10.0,
    sigma: float = 4.0,
    floor: float = _READABILITY_SCORE_FLOOR,
) -> float:
    """Compute readability score using Gaussian decay from target grade.

    Score is 100 at the target grade and decays symmetrically.
    Being too complex (higher grade) is penalised 1.5x harder than
    being too simple. A floor of 5.0 prevents single-dimension collapse
    in the composite score for extreme mismatches.

    Args:
        consensus_grade: The computed consensus readability grade (FK-equivalent).
        target_grade: The ideal grade level for the target audience.
        sigma: Controls the width of the tolerance band.
        floor: Minimum score (default 5.0) to prevent near-zero collapse.

    Returns:
        Score in [floor, 100] where 100 = perfect match to target.
    """
    deviation = consensus_grade - target_grade
    # Asymmetric: too complex penalised 1.5x harder
    effective_sigma = sigma * 1.5 if deviation > 0 else sigma * 2.5
    raw_score = 100.0 * math.exp(-((deviation / effective_sigma) ** 2))
    return max(floor, min(100.0, raw_score))


_GRADE_THRESHOLDS: list[tuple[float, str]] = [
    (85.0, "A"),
    (70.0, "B"),
    (55.0, "C"),
    (40.0, "D"),
]
"""Score thresholds for letter grades (checked high-to-low)."""

_STATUS_GOOD_THRESHOLD = 70.0
"""Scores above this value are ``good``."""

_STATUS_WARNING_THRESHOLD = 40.0
"""Scores at or above this value (and ≤ good threshold) are ``warning``."""


# --- Pure helper functions ---


def compute_letter_grade(score: float) -> str:
    """Map a composite score to a letter grade.

    Implements AC-FR-HEALTH-02.1.

    Args:
        score: Composite score in [0, 100].

    Returns:
        Letter grade: A (≥85), B (≥70), C (≥55), D (≥40), F (<40).
    """
    for threshold, grade in _GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "F"


def compute_status(score: float) -> str:
    """Map a dimension score to a status indicator.

    Implements AC-FR-HEALTH-01.4.

    Args:
        score: Dimension score in [0, 100].

    Returns:
        ``"good"`` when score > 70, ``"warning"`` when 40 ≤ score ≤ 70,
        ``"poor"`` when score < 40.
    """
    if score > _STATUS_GOOD_THRESHOLD:
        return "good"
    if score >= _STATUS_WARNING_THRESHOLD:
        return "warning"
    return "poor"


def redistribute_weights(
    weights: dict[str, float],
    exclude: list[str],
) -> dict[str, float]:
    """Remove excluded dimensions and redistribute their weight proportionally.

    Implements AC-FR-HEALTH-01.3.

    Args:
        weights: Current dimension weights (must sum to ~1.0).
        exclude: Dimension names to remove.

    Returns:
        New weight dict with excluded dimensions removed and remaining
        weights scaled to sum to 1.0.

    Raises:
        ValueError: If all dimensions would be excluded.
    """
    remaining = {k: v for k, v in weights.items() if k not in exclude}
    if not remaining:
        msg = "Cannot exclude all dimensions"
        raise ValueError(msg)
    total = sum(remaining.values())
    if total == 0.0:
        # All remaining weights are zero — distribute equally.
        equal = 1.0 / len(remaining)
        return dict.fromkeys(remaining, equal)
    scale = 1.0 / total
    return {k: v * scale for k, v in remaining.items()}


def get_focus_weights(focus: str) -> dict[str, float]:
    """Return dimension weights for a given focus mode.

    Implements AC-FR-HEALTH-04.1, AC-FR-HEALTH-04.2.

    Focus modes:
        - ``FULL``: default weights.
        - ``READABILITY``: readability 70%, remaining 30% split evenly.
        - ``NATURALNESS``: naturalness 70%, remaining 30% split evenly.
        - ``PERSONA_COMPLIANCE``: tone_compliance 70%, remaining 30% split evenly.

    Args:
        focus: Focus mode string (case-insensitive).

    Returns:
        Dimension weight dict summing to 1.0.
    """
    mode = focus.lower()
    if mode == FocusMode.FULL:
        return dict(DEFAULT_WEIGHTS)

    focus_map: dict[str, str] = {
        FocusMode.READABILITY: "readability",
        FocusMode.NATURALNESS: "naturalness",
        FocusMode.PERSONA_COMPLIANCE: "tone_compliance",
    }
    primary_dim = focus_map.get(mode)
    if primary_dim is None:
        # Unknown focus — fall back to default weights.
        return dict(DEFAULT_WEIGHTS)

    others = [d for d in DIMENSIONS if d != primary_dim]
    split = 0.30 / len(others)
    weights: dict[str, float] = {primary_dim: 0.70}
    for dim in others:
        weights[dim] = split
    return weights


# --- Main aggregation ---


def _resolve_active_weights(
    weights: dict[str, float] | None,
    focus: str,
    persona_weights: HealthScoreWeights | None,
    dimension_scores: dict[str, float | None],
    has_semantic: bool,
) -> dict[str, float]:
    """Resolve and redistribute dimension weights. FR-HEALTH-03."""
    if persona_weights is not None:
        active = {
            "readability": persona_weights.readability,
            "naturalness": persona_weights.naturalness,
            "vocabulary": persona_weights.vocabulary,
            "semantic_preservation": persona_weights.semantic_preservation,
            "tone_compliance": persona_weights.tone_compliance,
        }
    elif weights is not None:
        active = dict(weights)
    else:
        active = get_focus_weights(focus)

    exclude: list[str] = []
    if not has_semantic:
        exclude.append("semantic_preservation")
    for dim in DIMENSIONS:
        if dim not in exclude and dimension_scores.get(dim) is None:
            exclude.append(dim)

    if exclude:
        active = redistribute_weights(active, exclude)
    return active


def _build_dimension_breakdown(
    dimension_scores: dict[str, float | None],
    active_weights: dict[str, float],
) -> dict[str, DimensionScore | None]:
    """Build per-dimension DimensionScore breakdown."""
    dimensions: dict[str, DimensionScore | None] = {}
    for dim in DIMENSIONS:
        raw = dimension_scores.get(dim)
        if raw is None or dim not in active_weights:
            dimensions[dim] = None
        else:
            dimensions[dim] = DimensionScore(
                score=raw,
                status=compute_status(raw),
                weight=active_weights.get(dim, 0.0),
            )
    return dimensions


def aggregate_scores(  # noqa: PLR0913
    dimension_scores: dict[str, float | None],
    weights: dict[str, float] | None = None,
    focus: str = "full",
    has_semantic: bool = False,
    persona_weights: HealthScoreWeights | None = None,
    persona_name: str | None = None,
) -> HealthScore:
    """Aggregate per-dimension scores into a composite HealthScore.

    Implements FR-HEALTH-01, FR-HEALTH-02, FR-HEALTH-03, FR-HEALTH-04.

    Args:
        dimension_scores: Per-dimension raw scores (0-100). ``None`` means
            the dimension could not be computed.
        weights: Optional explicit weight overrides.
        focus: Focus mode string (default ``"full"``).
        has_semantic: Whether semantic preservation is available.
        persona_weights: Per-persona weight overrides from the persona schema.
        persona_name: Optional persona/channel name for readability targets.

    Returns:
        A ``HealthScore`` with composite score, letter grade, and
        per-dimension breakdown including status indicators.
    """
    active_weights = _resolve_active_weights(
        weights, focus, persona_weights, dimension_scores, has_semantic,
    )

    composite = 0.0
    for dim, w in active_weights.items():
        score = dimension_scores.get(dim)
        if score is not None:
            composite += score * w
    composite = round(min(max(composite, 0.0), 100.0), 1)

    dimensions = _build_dimension_breakdown(dimension_scores, active_weights)
    letter_grade = compute_letter_grade(composite)

    return HealthScore(
        composite_score=composite,
        letter_grade=letter_grade,
        dimensions=dimensions,
    )
