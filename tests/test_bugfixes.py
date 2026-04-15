"""Targeted tests for Bug 1 (next_steps min_length) and Bug 2 (rule violation flags).

Bug 1: ComparisonResult/AnalysisResult next_steps field had min_length=1,
    causing ValidationError when constructed with an empty list.
Bug 2: Persona rule violations were counted in PersonaAlignment but not
    surfaced as per-sentence Flag objects.
"""

from __future__ import annotations

from phraseturner.models.analysis import (
    AnalysisMetadata,
    AnalysisResult,
    ConciseAnalysisResult,
    DimensionScore,
    Flag,
    FlagsSummary,
    HealthScore,
)
from phraseturner.models.comparison import (
    ComparisonResult,
    ConciseComparisonResult,
    rebuild_comparison_models,
)
from phraseturner.personas.rules import RuleMatch
from phraseturner.personas.schema import (
    PersonaConfig,
    RuleConfig,
    ToneConfig,
    VocabularyConfig,
)
from phraseturner.pipeline.formatting import (
    _map_rule_matches_to_flags,
    format_output,
)

# Ensure forward references are resolved for comparison models.
rebuild_comparison_models()


def _make_metadata() -> AnalysisMetadata:
    """Create a minimal AnalysisMetadata for testing."""
    return AnalysisMetadata(
        model_versions={},
        latency_ms=10.0,
        token_count=5,
        operating_tier=1,
        t5_available=False,
    )


def _make_health_score() -> HealthScore:
    """Create a minimal HealthScore for testing."""
    return HealthScore(
        composite_score=75.0,
        letter_grade="B",
        dimensions={
            "readability": DimensionScore(score=80.0, status="good", weight=0.25),
        },
    )


# ===================================================================
# Bug 1: next_steps min_length=0 allows empty list
# ===================================================================


class TestBug1NextStepsEmptyList:
    """Verify that next_steps accepts an empty list (min_length removed)."""

    def test_comparison_result_empty_next_steps(self) -> None:
        """ComparisonResult should accept next_steps=[]."""
        result = ComparisonResult(
            semantic_similarity=0.9,
            health_score_delta={},
            overall_improvement=5.0,
            sentence_alignment=[],
            next_steps=[],
            metadata=_make_metadata(),
        )
        assert result.next_steps == []

    def test_concise_comparison_result_empty_next_steps(self) -> None:
        """ConciseComparisonResult should accept next_steps=[]."""
        result = ConciseComparisonResult(
            semantic_similarity=0.85,
            overall_improvement=3.0,
            next_steps=[],
            metadata=_make_metadata(),
        )
        assert result.next_steps == []

    def test_analysis_result_empty_next_steps(self) -> None:
        """AnalysisResult should accept next_steps=[]."""
        result = AnalysisResult(
            health_score=_make_health_score(),
            sentences=[],
            next_steps=[],
            metadata=_make_metadata(),
        )
        assert result.next_steps == []

    def test_concise_analysis_result_empty_next_steps(self) -> None:
        """ConciseAnalysisResult should accept next_steps=[]."""
        result = ConciseAnalysisResult(
            health_score=_make_health_score(),
            flags_summary=FlagsSummary(),
            next_steps=[],
            metadata=_make_metadata(),
        )
        assert result.next_steps == []

    def test_comparison_result_with_steps(self) -> None:
        """ComparisonResult should still accept 1-3 next_steps."""
        result = ComparisonResult(
            semantic_similarity=0.9,
            health_score_delta={},
            overall_improvement=5.0,
            sentence_alignment=[],
            next_steps=["step 1", "step 2"],
            metadata=_make_metadata(),
        )
        assert len(result.next_steps) == 2

    def test_comparison_result_default_factory(self) -> None:
        """ComparisonResult default_factory should produce empty list."""
        result = ComparisonResult(
            semantic_similarity=0.9,
            health_score_delta={},
            overall_improvement=5.0,
            sentence_alignment=[],
            metadata=_make_metadata(),
        )
        assert result.next_steps == []


# ===================================================================
# Bug 2: Rule violations surfaced as per-sentence flags
# ===================================================================


class TestBug2RuleViolationFlags:
    """Verify that persona rule violations appear as per-sentence Flag objects."""

    def test_map_rule_matches_to_flags_basic(self) -> None:
        """RuleMatch objects should be mapped to Flag objects on matching sentences."""
        match = RuleMatch(
            rule_id="no-memory-uris",
            rule_type="existence",
            level="error",
            message="Found memory:// URI",
            scope="text",
            matched_text="memory://",
        )
        sentence_texts = [
            "This is a normal sentence.",
            "Check the link at memory:// for details.",
            "Another clean sentence.",
        ]
        all_flags: list[list[Flag]] = [[], [], []]

        _map_rule_matches_to_flags([match], sentence_texts, all_flags)

        # Flag should be on sentence 1 (contains "memory://")
        assert len(all_flags[0]) == 0
        assert len(all_flags[1]) == 1
        assert all_flags[1][0].code == "RULE_no-memory-uris"
        assert all_flags[1][0].severity == "error"
        assert all_flags[1][0].message == "Found memory:// URI"
        assert len(all_flags[2]) == 0

    def test_map_rule_matches_fallback_to_first_sentence(self) -> None:
        """When matched_text isn't in any sentence, flag goes to first sentence."""
        match = RuleMatch(
            rule_id="test-rule",
            rule_type="existence",
            level="warning",
            message="Cross-sentence match",
            scope="text",
            matched_text="nonexistent fragment",
        )
        all_flags: list[list[Flag]] = [[], []]

        _map_rule_matches_to_flags([match], ["Hello.", "World."], all_flags)

        assert len(all_flags[0]) == 1
        assert all_flags[0][0].code == "RULE_test-rule"

    def test_map_rule_matches_multiple_sentences(self) -> None:
        """A match appearing in multiple sentences should flag all of them."""
        match = RuleMatch(
            rule_id="no-agent",
            rule_type="existence",
            level="warning",
            message="Found agent reference",
            scope="text",
            matched_text="invokeSubAgent",
        )
        sentence_texts = [
            "Use invokeSubAgent to delegate.",
            "Normal sentence here.",
            "Another invokeSubAgent call.",
        ]
        all_flags: list[list[Flag]] = [[], [], []]

        _map_rule_matches_to_flags([match], sentence_texts, all_flags)

        assert len(all_flags[0]) == 1
        assert len(all_flags[1]) == 0
        assert len(all_flags[2]) == 1

    def test_format_output_includes_rule_violation_flags(self) -> None:
        """format_output should include rule violation flags in per-sentence flags."""
        persona = PersonaConfig(
            name="internal-references",
            version="1.0.0",
            tone=ToneConfig(formality=0.5),
            vocabulary=VocabularyConfig(),
            rules=[
                RuleConfig(
                    id="no-memory-uris",
                    type="existence",
                    level="error",
                    message="Internal memory:// URI detected",
                    raw=["memory://"],
                ),
            ],
        )
        analysis_data = {
            "sentences": [
                {"word_count": 8, "text": "This is a normal sentence here now."},
                {"word_count": 10, "text": "See memory:// for the full context of this."},
            ],
            "tone_scores": {"formality": 0.5},
        }

        all_flags, _suggestions, alignment = format_output(
            analysis_data,
            persona=persona,
            text="This is a normal sentence here now. See memory:// for the full context of this.",
            sentences=[
                "This is a normal sentence here now.",
                "See memory:// for the full context of this.",
            ],
        )

        # Sentence 1 should have a RULE_no-memory-uris flag
        sent1_codes = [f.code for f in all_flags[1]]
        assert "RULE_no-memory-uris" in sent1_codes

        # Alignment should still count the violation
        assert alignment is not None
        assert alignment.rule_violations >= 1

    def test_format_output_no_rule_flags_without_persona(self) -> None:
        """Without a persona, no rule violation flags should appear."""
        analysis_data = {
            "sentences": [
                {"word_count": 10, "text": "See memory:// for details about this."},
            ],
        }

        all_flags, _, alignment = format_output(analysis_data)

        # No RULE_ flags without a persona
        for flags in all_flags:
            assert not any(f.code.startswith("RULE_") for f in flags)
        assert alignment is None
