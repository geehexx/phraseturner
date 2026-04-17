"""Unit tests for Stage 4: Score aggregation.

Tests cover:
- compute_letter_grade boundary values
- compute_status boundary values
- redistribute_weights proportional redistribution
- get_focus_weights for all focus modes
- aggregate_scores with defaults, persona overrides, focus modes, and None handling
"""

from __future__ import annotations

import pytest

from phraseturner.personas.schema import HealthScoreWeights
from phraseturner.pipeline.scoring import (
    CHANNEL_READABILITY_TARGETS,
    DEFAULT_WEIGHTS,
    DIMENSIONS,
    aggregate_scores,
    compute_letter_grade,
    compute_status,
    gaussian_readability_score,
    get_focus_weights,
    redistribute_weights,
)

# --- compute_letter_grade ---


class TestComputeLetterGrade:
    """Tests for letter grade assignment. Validates AC-FR-HEALTH-02.1."""

    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            (100.0, "A"),
            (85.0, "A"),
            (84.9, "B"),
            (70.0, "B"),
            (69.9, "C"),
            (55.0, "C"),
            (54.9, "D"),
            (40.0, "D"),
            (39.9, "F"),
            (0.0, "F"),
        ],
    )
    def test_grade_boundaries(self, score: float, expected: str) -> None:
        assert compute_letter_grade(score) == expected


# --- compute_status ---


class TestComputeStatus:
    """Tests for status indicator assignment. Validates AC-FR-HEALTH-01.4."""

    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            (100.0, "good"),
            (70.1, "good"),
            (70.0, "warning"),  # boundary: 70.0 is NOT > 70
            (40.0, "warning"),
            (39.9, "poor"),
            (0.0, "poor"),
        ],
    )
    def test_status_boundaries(self, score: float, expected: str) -> None:
        assert compute_status(score) == expected


# --- redistribute_weights ---


class TestRedistributeWeights:
    """Tests for weight redistribution. Validates AC-FR-HEALTH-01.3."""

    def test_exclude_semantic_preservation(self) -> None:
        result = redistribute_weights(DEFAULT_WEIGHTS, ["semantic_preservation"])
        assert "semantic_preservation" not in result
        assert abs(sum(result.values()) - 1.0) < 1e-9

    def test_proportional_redistribution(self) -> None:
        """Remaining weights keep their relative proportions."""
        result = redistribute_weights(DEFAULT_WEIGHTS, ["semantic_preservation"])
        # readability was 0.25, naturalness 0.30 — ratio should be 25:30
        ratio = result["readability"] / result["naturalness"]
        expected_ratio = 0.25 / 0.30
        assert abs(ratio - expected_ratio) < 1e-9

    def test_exclude_multiple(self) -> None:
        result = redistribute_weights(
            DEFAULT_WEIGHTS,
            ["semantic_preservation", "tone_compliance"],
        )
        assert len(result) == 3
        assert abs(sum(result.values()) - 1.0) < 1e-9

    def test_exclude_all_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot exclude all"):
            redistribute_weights(DEFAULT_WEIGHTS, list(DEFAULT_WEIGHTS.keys()))

    def test_zero_weight_remaining(self) -> None:
        """When all remaining weights are zero, distribute equally."""
        weights = {"a": 0.0, "b": 0.0, "c": 1.0}
        result = redistribute_weights(weights, ["c"])
        assert abs(result["a"] - 0.5) < 1e-9
        assert abs(result["b"] - 0.5) < 1e-9


# --- get_focus_weights ---


class TestGetFocusWeights:
    """Tests for focus mode weight generation. Validates FR-HEALTH-04."""

    def test_full_returns_defaults(self) -> None:
        result = get_focus_weights("full")
        assert result == DEFAULT_WEIGHTS

    def test_readability_focus(self) -> None:
        result = get_focus_weights("readability")
        assert abs(result["readability"] - 0.70) < 1e-9
        assert abs(sum(result.values()) - 1.0) < 1e-9

    def test_naturalness_focus(self) -> None:
        result = get_focus_weights("naturalness")
        assert abs(result["naturalness"] - 0.70) < 1e-9
        assert abs(sum(result.values()) - 1.0) < 1e-9

    def test_persona_compliance_focus(self) -> None:
        result = get_focus_weights("persona_compliance")
        assert abs(result["tone_compliance"] - 0.70) < 1e-9
        assert abs(sum(result.values()) - 1.0) < 1e-9

    def test_unknown_focus_returns_defaults(self) -> None:
        result = get_focus_weights("unknown_mode")
        assert result == DEFAULT_WEIGHTS

    def test_case_insensitive(self) -> None:
        result = get_focus_weights("READABILITY")
        assert abs(result["readability"] - 0.70) < 1e-9


# --- aggregate_scores ---


class TestAggregateScores:
    """Tests for the main aggregation function. Validates FR-HEALTH-01 through 04."""

    @pytest.fixture()
    def all_scores(self) -> dict[str, float | None]:
        return {
            "readability": 80.0,
            "naturalness": 60.0,
            "vocabulary": 70.0,
            "semantic_preservation": 90.0,
            "tone_compliance": 50.0,
        }

    @pytest.fixture()
    def four_scores(self) -> dict[str, float | None]:
        """Scores without semantic preservation (typical standalone check)."""
        return {
            "readability": 80.0,
            "naturalness": 60.0,
            "vocabulary": 70.0,
            "tone_compliance": 50.0,
        }

    def test_default_weights_with_semantic(
        self, all_scores: dict[str, float | None],
    ) -> None:
        result = aggregate_scores(all_scores, has_semantic=True)
        # 80*0.25 + 60*0.30 + 70*0.20 + 90*0.15 + 50*0.10 = 20+18+14+13.5+5 = 70.5
        assert result.composite_score == 70.5
        assert result.letter_grade == "B"

    def test_semantic_excluded_when_no_original(
        self, four_scores: dict[str, float | None],
    ) -> None:
        result = aggregate_scores(four_scores, has_semantic=False)
        assert result.dimensions["semantic_preservation"] is None
        # Weights redistributed: 0.25/0.85, 0.30/0.85, 0.20/0.85, 0.10/0.85
        scored_dims = [
            d for d in DIMENSIONS
            if result.dimensions[d] is not None
        ]
        assert len(scored_dims) == 4
        # Verify weights sum to 1.0
        total_weight = sum(
            result.dimensions[d].weight  # type: ignore[union-attr]
            for d in scored_dims
        )
        assert abs(total_weight - 1.0) < 1e-6

    def test_persona_weight_overrides(
        self, all_scores: dict[str, float | None],
    ) -> None:
        pw = HealthScoreWeights(
            readability=0.40,
            naturalness=0.20,
            vocabulary=0.15,
            semantic_preservation=0.15,
            tone_compliance=0.10,
        )
        result = aggregate_scores(
            all_scores, has_semantic=True, persona_weights=pw,
        )
        # 80*0.40 + 60*0.20 + 70*0.15 + 90*0.15 + 50*0.10 = 32+12+10.5+13.5+5 = 73.0
        assert result.composite_score == 73.0
        assert result.letter_grade == "B"

    def test_focus_readability(
        self, four_scores: dict[str, float | None],
    ) -> None:
        result = aggregate_scores(
            four_scores, focus="readability", has_semantic=False,
        )
        # readability gets 0.70 base, but semantic excluded → redistributed
        rd = result.dimensions["readability"]
        assert rd is not None
        assert rd.weight > 0.5  # readability should dominate

    def test_none_dimension_excluded(self) -> None:
        scores: dict[str, float | None] = {
            "readability": 80.0,
            "naturalness": None,
            "vocabulary": 70.0,
            "tone_compliance": 50.0,
        }
        result = aggregate_scores(scores, has_semantic=False)
        assert result.dimensions["naturalness"] is None
        assert result.dimensions["semantic_preservation"] is None
        scored = [
            d for d in DIMENSIONS
            if result.dimensions[d] is not None
        ]
        assert len(scored) == 3

    def test_all_dimensions_none_except_one(self) -> None:
        scores: dict[str, float | None] = {
            "readability": 85.0,
        }
        result = aggregate_scores(scores, has_semantic=False)
        assert result.composite_score == 85.0
        assert result.letter_grade == "A"

    def test_status_indicators(
        self, all_scores: dict[str, float | None],
    ) -> None:
        result = aggregate_scores(all_scores, has_semantic=True)
        rd = result.dimensions["readability"]
        assert rd is not None
        assert rd.status == "good"  # 80 > 70
        tc = result.dimensions["tone_compliance"]
        assert tc is not None
        assert tc.status == "warning"  # 50 is 40-70

    def test_composite_clamped_to_100(self) -> None:
        scores: dict[str, float | None] = {
            "readability": 100.0,
            "naturalness": 100.0,
            "vocabulary": 100.0,
            "tone_compliance": 100.0,
        }
        result = aggregate_scores(scores, has_semantic=False)
        assert result.composite_score <= 100.0

    def test_explicit_weights_override(self) -> None:
        scores: dict[str, float | None] = {
            "readability": 100.0,
            "naturalness": 0.0,
            "vocabulary": 0.0,
            "tone_compliance": 0.0,
        }
        custom = {
            "readability": 1.0,
            "naturalness": 0.0,
            "vocabulary": 0.0,
            "tone_compliance": 0.0,
        }
        result = aggregate_scores(
            scores, weights=custom, has_semantic=False,
        )
        assert result.composite_score == 100.0



# --- gaussian_readability_score ---


class TestGaussianReadabilityScore:
    """Tests for Gaussian decay readability scoring."""

    def test_perfect_match_returns_100(self) -> None:
        """Score is 100 when consensus grade equals target."""
        assert gaussian_readability_score(10.0, target_grade=10.0) == pytest.approx(100.0)

    def test_symmetric_decay_below_target(self) -> None:
        """Score decays when grade is below target (too simple)."""
        score = gaussian_readability_score(6.0, target_grade=10.0, sigma=4.0)
        assert 0.0 < score < 100.0

    def test_symmetric_decay_above_target(self) -> None:
        """Score decays when grade is above target (too complex)."""
        score = gaussian_readability_score(14.0, target_grade=10.0, sigma=4.0)
        assert 0.0 < score < 100.0

    def test_asymmetric_penalty(self) -> None:
        """Too complex is penalised harder than too simple at same deviation."""
        too_simple = gaussian_readability_score(6.0, target_grade=10.0, sigma=4.0)
        too_complex = gaussian_readability_score(14.0, target_grade=10.0, sigma=4.0)
        # Same absolute deviation (4), but too_complex should score lower
        assert too_complex < too_simple

    def test_far_from_target_hits_floor(self) -> None:
        """Very large deviation produces the floor score (5.0), not near-zero."""
        score = gaussian_readability_score(30.0, target_grade=10.0, sigma=4.0)
        assert score >= 5.0
        assert score == pytest.approx(5.0)  # floor applied

    def test_clamped_to_0_100(self) -> None:
        """Score is always in [0, 100]."""
        assert 0.0 <= gaussian_readability_score(0.0) <= 100.0
        assert 0.0 <= gaussian_readability_score(50.0) <= 100.0
        assert 0.0 <= gaussian_readability_score(-5.0) <= 100.0

    def test_known_value_below_target(self) -> None:
        """Verify a known computation: grade=6, target=10, sigma=4.

        deviation = -4, effective_sigma = 4*2.5 = 10.0
        score = 100 * exp(-(-4/10)^2) = 100 * exp(-0.16) ≈ 85.21
        """
        score = gaussian_readability_score(6.0, target_grade=10.0, sigma=4.0)
        assert score == pytest.approx(85.21, abs=0.1)

    def test_known_value_above_target(self) -> None:
        """Verify a known computation: grade=14, target=10, sigma=4.

        deviation = +4, effective_sigma = 4*1.5 = 6.0
        score = 100 * exp(-(4/6)^2) = 100 * exp(-0.4444) ≈ 64.12
        """
        score = gaussian_readability_score(14.0, target_grade=10.0, sigma=4.0)
        assert score == pytest.approx(64.12, abs=0.1)

    def test_channel_targets_exist(self) -> None:
        """All expected channels are present in the targets dict."""
        expected = {
            "slack-casual", "jira-ticket", "pr-review",
            "confluence-docs", "technical-docs", "email-professional",
            "blog-post", "executive-summary",
        }
        assert set(CHANNEL_READABILITY_TARGETS.keys()) == expected

    def test_channel_target_values(self) -> None:
        """Spot-check channel target values."""
        assert CHANNEL_READABILITY_TARGETS["slack-casual"] == (7.0, 2.0)
        assert CHANNEL_READABILITY_TARGETS["technical-docs"] == (14.0, 3.0)
        assert CHANNEL_READABILITY_TARGETS["pr-review"] == (12.0, 3.0)

    def test_with_channel_target(self) -> None:
        """Score using a channel-specific target."""
        target, sigma = CHANNEL_READABILITY_TARGETS["slack-casual"]
        score = gaussian_readability_score(7.0, target_grade=target, sigma=sigma)
        assert score == pytest.approx(100.0)


# --- aggregate_scores with persona_name ---


class TestAggregateScoresPersonaName:
    """Tests for aggregate_scores with the persona_name parameter."""

    def test_persona_name_accepted(self) -> None:
        """aggregate_scores accepts persona_name without error."""
        scores: dict[str, float | None] = {
            "readability": 80.0,
            "naturalness": 60.0,
            "vocabulary": 70.0,
            "tone_compliance": 50.0,
        }
        result = aggregate_scores(
            scores, has_semantic=False, persona_name="slack-casual",
        )
        assert result.composite_score > 0.0

    def test_persona_name_none_works(self) -> None:
        """aggregate_scores works with persona_name=None (default)."""
        scores: dict[str, float | None] = {
            "readability": 80.0,
            "naturalness": 60.0,
            "vocabulary": 70.0,
            "tone_compliance": 50.0,
        }
        result = aggregate_scores(scores, has_semantic=False, persona_name=None)
        assert result.composite_score > 0.0
