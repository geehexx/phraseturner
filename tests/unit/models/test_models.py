"""Tests for phraseturner data models — validation, constraints, round-trips.

Validates: NFR-QUAL-04.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from phraseturner.models.analysis import (
    AnalysisMetadata,
    AnalysisResult,
    ConciseAnalysisResult,
    DimensionScore,
    Flag,
    FlagsSummary,
    HealthScore,
    ResponseFormat,
    Suggestion,
)
from phraseturner.models.comparison import (
    ComparisonResult,
    DimensionDelta,
    SentenceAlignment,
    rebuild_comparison_models,
)
from phraseturner.models.errors import AnalysisError, ToolError
from phraseturner.models.inputs import AnalyzeInput, FocusMode
from phraseturner.models.persona import (
    PersonaCreateResult,
    PersonaSummary,
    ValidationResult,
)
from phraseturner.models.persona import (
    ValidationError as PersonaValidationError,
)

# ---------------------------------------------------------------------------
# DimensionScore constraints
# ---------------------------------------------------------------------------


class TestDimensionScore:
    """DimensionScore field constraints (ge/le)."""

    def test_valid_score(self) -> None:
        ds = DimensionScore(score=75.0, status="good", weight=0.25)
        assert ds.score == 75.0

    def test_score_at_boundaries(self) -> None:
        low = DimensionScore(score=0.0, status="poor", weight=0.0)
        high = DimensionScore(score=100.0, status="good", weight=1.0)
        assert low.score == 0.0
        assert high.score == 100.0

    def test_score_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DimensionScore(score=-1.0, status="poor", weight=0.25)

    def test_score_above_100_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DimensionScore(score=101.0, status="good", weight=0.25)

    def test_weight_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DimensionScore(score=50.0, status="warning", weight=-0.1)

    def test_weight_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DimensionScore(score=50.0, status="warning", weight=1.1)

    def test_round_trip(self) -> None:
        ds = DimensionScore(score=42.5, status="warning", weight=0.3)
        data = ds.model_dump()
        restored = DimensionScore.model_validate(data)
        assert restored == ds


# ---------------------------------------------------------------------------
# HealthScore
# ---------------------------------------------------------------------------


class TestHealthScore:
    """HealthScore composite_score constraints and round-trip."""

    def test_valid_health_score(self) -> None:
        hs = HealthScore(
            composite_score=72.5,
            letter_grade="B",
            dimensions={"readability": DimensionScore(score=80.0, status="good", weight=0.25)},
        )
        assert hs.composite_score == 72.5

    def test_composite_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            HealthScore(composite_score=-5.0, letter_grade="F", dimensions={})

    def test_composite_above_100_rejected(self) -> None:
        with pytest.raises(ValidationError):
            HealthScore(composite_score=105.0, letter_grade="A", dimensions={})

    def test_none_dimension_allowed(self) -> None:
        hs = HealthScore(
            composite_score=50.0,
            letter_grade="C",
            dimensions={"semantic_preservation": None},
        )
        assert hs.dimensions["semantic_preservation"] is None

    def test_round_trip(self) -> None:
        hs = HealthScore(
            composite_score=85.0,
            letter_grade="A",
            dimensions={
                "readability": DimensionScore(score=90.0, status="good", weight=0.25),
                "naturalness": None,
            },
        )
        data = hs.model_dump()
        restored = HealthScore.model_validate(data)
        assert restored.composite_score == hs.composite_score
        assert restored.letter_grade == hs.letter_grade


# ---------------------------------------------------------------------------
# Flag and Suggestion
# ---------------------------------------------------------------------------


class TestFlag:
    """Flag model validation."""

    def test_valid_flag(self) -> None:
        f = Flag(code="PASSIVE_VOICE", severity="warning", message="Passive construction detected")
        assert f.code == "PASSIVE_VOICE"

    def test_round_trip(self) -> None:
        f = Flag(code="LONG_SENTENCE", severity="error", message="Sentence too long")
        restored = Flag.model_validate(f.model_dump())
        assert restored == f


class TestSuggestion:
    """Suggestion model validation."""

    def test_valid_suggestion(self) -> None:
        s = Suggestion(
            sentence_index=0,
            flag_code="FORMAL_IN_CASUAL",
            hint="Use casual language",
            impact=0.85,
        )
        assert s.impact == 0.85

    def test_round_trip(self) -> None:
        s = Suggestion(sentence_index=1, flag_code="X", hint="hint", impact=0.5)
        restored = Suggestion.model_validate(s.model_dump())
        assert restored == s


# ---------------------------------------------------------------------------
# AnalysisMetadata
# ---------------------------------------------------------------------------


class TestAnalysisMetadata:
    """AnalysisMetadata defaults and round-trip."""

    def test_defaults(self) -> None:
        m = AnalysisMetadata(
            model_versions={"spacy": "3.8.4"},
            latency_ms=100.0,
            token_count=50,
            operating_tier=4,
            t5_available=True,
        )
        assert m.degraded is False
        assert m.failed_stages is None

    def test_degraded_mode(self) -> None:
        m = AnalysisMetadata(
            model_versions={},
            latency_ms=50.0,
            token_count=10,
            operating_tier=1,
            t5_available=False,
            degraded=True,
            failed_stages=["stage3"],
        )
        assert m.degraded is True
        assert m.failed_stages == ["stage3"]

    def test_round_trip(self) -> None:
        m = AnalysisMetadata(
            model_versions={"spacy": "3.8.4", "t5": "flan-t5-base"},
            latency_ms=312.5,
            token_count=15,
            operating_tier=4,
            t5_available=True,
        )
        restored = AnalysisMetadata.model_validate(m.model_dump())
        assert restored == m


# ---------------------------------------------------------------------------
# ComparisonResult (requires model rebuild for forward refs)
# ---------------------------------------------------------------------------


class TestComparisonModels:
    """Comparison model validation and round-trip."""

    @classmethod
    def setup_class(cls) -> None:
        rebuild_comparison_models()

    def test_dimension_delta_round_trip(self) -> None:
        dd = DimensionDelta(original=45.0, rewritten=78.0, delta=33.0)
        restored = DimensionDelta.model_validate(dd.model_dump())
        assert restored == dd

    def test_sentence_alignment_round_trip(self) -> None:
        sa = SentenceAlignment(original_index=0, rewritten_indices=[0, 1], similarity=0.82)
        restored = SentenceAlignment.model_validate(sa.model_dump())
        assert restored == sa

    def test_semantic_similarity_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ComparisonResult(
                semantic_similarity=-0.1,
                health_score_delta={},
                overall_improvement=0.0,
                sentence_alignment=[],
                next_steps=["step"],
                metadata=AnalysisMetadata(
                    model_versions={},
                    latency_ms=0,
                    token_count=0,
                    operating_tier=0,
                    t5_available=False,
                ),
            )

    def test_semantic_similarity_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ComparisonResult(
                semantic_similarity=1.5,
                health_score_delta={},
                overall_improvement=0.0,
                sentence_alignment=[],
                next_steps=["step"],
                metadata=AnalysisMetadata(
                    model_versions={},
                    latency_ms=0,
                    token_count=0,
                    operating_tier=0,
                    t5_available=False,
                ),
            )


# ---------------------------------------------------------------------------
# ToolError and AnalysisError
# ---------------------------------------------------------------------------


class TestToolError:
    """ToolError model validation."""

    def test_valid_tool_error(self) -> None:
        te = ToolError(code="TEXT_TOO_LONG", message="Too long")
        assert te.details is None

    def test_with_details(self) -> None:
        te = ToolError(code="X", message="msg", details={"key": "val"})
        assert te.details == {"key": "val"}

    def test_round_trip(self) -> None:
        te = ToolError(code="PERSONA_NOT_FOUND", message="Not found", details={"q": "x"})
        restored = ToolError.model_validate(te.model_dump())
        assert restored == te


class TestAnalysisError:
    """AnalysisError model validation."""

    def test_defaults(self) -> None:
        ae = AnalysisError(code="STAGE_FAILED", message="Stage 3 failed")
        assert ae.details is None
        assert ae.partial_results is None

    def test_with_partial_results(self) -> None:
        ae = AnalysisError(
            code="STAGE_FAILED",
            message="Stage 3 failed",
            partial_results={"health_score": 42},
        )
        assert ae.partial_results == {"health_score": 42}


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


class TestFocusMode:
    """FocusMode enum values."""

    def test_all_values(self) -> None:
        assert FocusMode.FULL.value == "full"
        assert FocusMode.READABILITY.value == "readability"
        assert FocusMode.NATURALNESS.value == "naturalness"
        assert FocusMode.PERSONA_COMPLIANCE.value == "persona_compliance"


class TestResponseFormat:
    """ResponseFormat enum values."""

    def test_values(self) -> None:
        assert ResponseFormat.CONCISE.value == "concise"
        assert ResponseFormat.DETAILED.value == "detailed"


class TestAnalyzeInput:
    """AnalyzeInput validation."""

    def test_minimal_valid(self) -> None:
        inp = AnalyzeInput(text="Hello world.")
        assert inp.persona is None
        assert inp.focus == FocusMode.FULL
        assert inp.include_suggestions is False
        assert inp.response_format == ResponseFormat.DETAILED

    def test_empty_text_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AnalyzeInput(text="")

    def test_all_fields(self) -> None:
        inp = AnalyzeInput(
            text="Some text.",
            persona="slack-casual",
            focus=FocusMode.READABILITY,
            include_suggestions=True,
            original_text="Original.",
            response_format=ResponseFormat.CONCISE,
        )
        assert inp.persona == "slack-casual"
        assert inp.focus == FocusMode.READABILITY


# ---------------------------------------------------------------------------
# Persona output models
# ---------------------------------------------------------------------------


class TestPersonaSummary:
    """PersonaSummary round-trip."""

    def test_round_trip(self) -> None:
        ps = PersonaSummary(
            name="test",
            description="A test persona",
            tags=["test"],
            channels=[],
            tier="built-in",
            version="1.0.0",
        )
        restored = PersonaSummary.model_validate(ps.model_dump())
        assert restored == ps


class TestPersonaCreateResult:
    """PersonaCreateResult round-trip."""

    def test_round_trip(self) -> None:
        pcr = PersonaCreateResult(
            name="new-persona",
            file_path="/home/user/personas/new-persona.yaml",
            validation=ValidationResult(valid=True, errors=[], warnings=[]),
        )
        restored = PersonaCreateResult.model_validate(pcr.model_dump())
        assert restored == pcr


class TestValidationResult:
    """ValidationResult round-trip."""

    def test_valid_result(self) -> None:
        vr = ValidationResult(valid=True, errors=[], warnings=[])
        assert vr.valid is True

    def test_invalid_result(self) -> None:
        err = PersonaValidationError(
            path="persona.name",
            code="MISSING_REQUIRED_FIELD",
            message="name is required",
        )
        vr = ValidationResult(valid=False, errors=[err], warnings=[])
        assert vr.valid is False
        assert len(vr.errors) == 1


# ---------------------------------------------------------------------------
# Regression: Bug 1 — next_steps min_length=0 allows empty list
# ---------------------------------------------------------------------------


def _make_metadata() -> AnalysisMetadata:
    """Create a minimal AnalysisMetadata for regression tests."""
    return AnalysisMetadata(
        model_versions={},
        latency_ms=10.0,
        token_count=5,
        operating_tier=1,
        t5_available=False,
    )


def _make_health_score() -> HealthScore:
    """Create a minimal HealthScore for regression tests."""
    return HealthScore(
        composite_score=75.0,
        letter_grade="B",
        dimensions={
            "readability": DimensionScore(score=80.0, status="good", weight=0.25),
        },
    )


class TestNextStepsEmptyList:
    """Verify that next_steps accepts an empty list (min_length removed).

    Regression test for Bug 1: ComparisonResult/AnalysisResult next_steps
    field had min_length=1, causing ValidationError when constructed with
    an empty list.
    """

    def test_comparison_result_empty_next_steps(self) -> None:
        """ComparisonResult should accept next_steps=[]."""
        from phraseturner.models.comparison import ComparisonResult, rebuild_comparison_models

        rebuild_comparison_models()
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
        from phraseturner.models.comparison import (
            ConciseComparisonResult,
            rebuild_comparison_models,
        )

        rebuild_comparison_models()
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
        from phraseturner.models.comparison import ComparisonResult, rebuild_comparison_models

        rebuild_comparison_models()
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
        from phraseturner.models.comparison import ComparisonResult, rebuild_comparison_models

        rebuild_comparison_models()
        result = ComparisonResult(
            semantic_similarity=0.9,
            health_score_delta={},
            overall_improvement=5.0,
            sentence_alignment=[],
            metadata=_make_metadata(),
        )
        assert result.next_steps == []
