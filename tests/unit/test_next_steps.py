"""Tests for phraseturner.next_steps — NextStepsBuilder methods.

Validates: NFR-QUAL-04.
"""

from __future__ import annotations

from phraseturner.models.analysis import (
    AnalysisMetadata,
    AnalysisResult,
    DimensionScore,
    HealthScore,
    PersonaAlignment,
)
from phraseturner.models.comparison import ComparisonResult, rebuild_comparison_models
from phraseturner.next_steps import NextStepsBuilder

rebuild_comparison_models()

_builder = NextStepsBuilder()


def _make_metadata() -> AnalysisMetadata:
    return AnalysisMetadata(
        model_versions={},
        latency_ms=10.0,
        token_count=5,
        operating_tier=1,
        t5_available=False,
    )


def _make_health_score(
    composite: float,
    grade: str,
    naturalness_status: str = "good",
) -> HealthScore:
    return HealthScore(
        composite_score=composite,
        letter_grade=grade,
        dimensions={
            "readability": DimensionScore(score=80.0, status="good", weight=0.25),
            "naturalness": DimensionScore(
                score=50.0 if naturalness_status != "good" else 80.0,
                status=naturalness_status,
                weight=0.30,
            ),
        },
    )


def _make_analysis_result(
    grade: str = "B",
    composite: float = 72.0,
    naturalness_status: str = "good",
    persona_alignment: PersonaAlignment | None = None,
) -> AnalysisResult:
    return AnalysisResult(
        health_score=_make_health_score(composite, grade, naturalness_status),
        sentences=[],
        persona_alignment=persona_alignment,
        next_steps=["placeholder"],
        metadata=_make_metadata(),
    )


# ---------------------------------------------------------------------------
# for_analysis
# ---------------------------------------------------------------------------


class TestForAnalysis:
    """NextStepsBuilder.for_analysis returns 1-3 suggestions."""

    def test_good_score_returns_no_action(self) -> None:
        result = _make_analysis_result(grade="A", composite=90.0)
        steps = _builder.for_analysis(result, persona=None)
        assert 1 <= len(steps) <= 3
        assert "good" in steps[0].lower() or "no immediate" in steps[0].lower()

    def test_poor_grade_suggests_rewrite(self) -> None:
        result = _make_analysis_result(grade="D", composite=35.0)
        steps = _builder.for_analysis(result, persona=None)
        assert any("rewrite" in s.lower() or "score" in s.lower() for s in steps)

    def test_low_persona_compliance_suggests_get_persona(self) -> None:
        alignment = PersonaAlignment(
            overall_compliance=0.2,
            tone_deltas={},
            rule_violations=3,
            rule_passes=0,
        )
        result = _make_analysis_result(
            grade="C",
            composite=55.0,
            persona_alignment=alignment,
        )
        steps = _builder.for_analysis(result, persona="slack-casual")
        assert any("get_persona" in s for s in steps)

    def test_poor_naturalness_suggests_vary_sentences(self) -> None:
        result = _make_analysis_result(
            grade="C",
            composite=55.0,
            naturalness_status="poor",
        )
        steps = _builder.for_analysis(result, persona=None)
        assert any("naturalness" in s.lower() or "sentence" in s.lower() for s in steps)

    def test_max_three_steps(self) -> None:
        alignment = PersonaAlignment(
            overall_compliance=0.1,
            tone_deltas={},
            rule_violations=5,
            rule_passes=0,
        )
        result = _make_analysis_result(
            grade="F",
            composite=20.0,
            naturalness_status="poor",
            persona_alignment=alignment,
        )
        steps = _builder.for_analysis(result, persona="test")
        assert len(steps) <= 3


# ---------------------------------------------------------------------------
# for_comparison
# ---------------------------------------------------------------------------


class TestForComparison:
    """NextStepsBuilder.for_comparison returns 1-3 suggestions."""

    def _make_comparison(
        self,
        improvement: float = 10.0,
        similarity: float = 0.85,
    ) -> ComparisonResult:
        return ComparisonResult(
            semantic_similarity=similarity,
            health_score_delta={},
            overall_improvement=improvement,
            sentence_alignment=[],
            next_steps=["placeholder"],
            metadata=_make_metadata(),
        )

    def test_regression_warns(self) -> None:
        result = self._make_comparison(improvement=-5.0)
        steps = _builder.for_comparison(result)
        assert any("regress" in s.lower() for s in steps)

    def test_meaning_drift_warns(self) -> None:
        result = self._make_comparison(similarity=0.5)
        steps = _builder.for_comparison(result)
        assert any("meaning" in s.lower() or "drift" in s.lower() for s in steps)

    def test_strong_improvement_confirms(self) -> None:
        result = self._make_comparison(improvement=25.0)
        steps = _builder.for_comparison(result)
        assert any("improvement" in s.lower() or "score" in s.lower() for s in steps)

    def test_moderate_improvement_suggests_iteration(self) -> None:
        result = self._make_comparison(improvement=10.0, similarity=0.85)
        steps = _builder.for_comparison(result)
        assert 1 <= len(steps) <= 3


# ---------------------------------------------------------------------------
# for_score
# ---------------------------------------------------------------------------


class TestForScore:
    """NextStepsBuilder.for_score returns 1-3 suggestions."""

    def test_poor_grade_suggests_analyze(self) -> None:
        hs = _make_health_score(30.0, "F")
        steps = _builder.for_score(hs)
        assert any("analyze" in s.lower() for s in steps)

    def test_b_grade_identifies_weakest(self) -> None:
        hs = _make_health_score(72.0, "B")
        steps = _builder.for_score(hs)
        assert 1 <= len(steps) <= 3

    def test_a_grade_confirms_quality(self) -> None:
        hs = _make_health_score(90.0, "A")
        steps = _builder.for_score(hs)
        assert any("strong" in s.lower() or "good" in s.lower() or "A" in s for s in steps)


# ---------------------------------------------------------------------------
# Persona tool next steps
# ---------------------------------------------------------------------------


class TestForPersonaTools:
    """NextStepsBuilder persona tool methods return 1-3 suggestions."""

    def test_list_personas_empty(self) -> None:
        steps = _builder.for_list_personas(0)
        assert any("create_persona" in s for s in steps)

    def test_list_personas_non_empty(self) -> None:
        steps = _builder.for_list_personas(5)
        assert any("get_persona" in s for s in steps)
        assert 1 <= len(steps) <= 3

    def test_get_persona(self) -> None:
        steps = _builder.for_get_persona("slack-casual")
        assert any("analyze" in s.lower() for s in steps)
        assert 1 <= len(steps) <= 3

    def test_create_persona(self) -> None:
        steps = _builder.for_create_persona("my-persona")
        assert any("analyze" in s.lower() or "get_persona" in s.lower() for s in steps)
        assert 1 <= len(steps) <= 3

    def test_validate_persona_valid(self) -> None:
        steps = _builder.for_validate_persona(valid=True)
        assert any("create_persona" in s for s in steps)

    def test_validate_persona_invalid(self) -> None:
        steps = _builder.for_validate_persona(valid=False)
        assert any("fix" in s.lower() or "validate" in s.lower() for s in steps)


# ---------------------------------------------------------------------------
# for_error
# ---------------------------------------------------------------------------


class TestForError:
    """NextStepsBuilder.for_error returns recovery suggestions."""

    def test_text_too_long(self) -> None:
        steps = _builder.for_error("TEXT_TOO_LONG")
        assert any("8000" in s or "token" in s.lower() for s in steps)

    def test_text_too_short(self) -> None:
        steps = _builder.for_error("TEXT_TOO_SHORT")
        assert len(steps) >= 1

    def test_persona_not_found(self) -> None:
        steps = _builder.for_error("PERSONA_NOT_FOUND")
        assert any("list_personas" in s for s in steps)

    def test_persona_exists(self) -> None:
        steps = _builder.for_error("PERSONA_EXISTS")
        assert len(steps) >= 1

    def test_persona_validation_failed(self) -> None:
        steps = _builder.for_error("PERSONA_VALIDATION_FAILED")
        assert any("validate" in s.lower() for s in steps)

    def test_unknown_code_returns_generic(self) -> None:
        steps = _builder.for_error("UNKNOWN_CODE_XYZ")
        assert len(steps) >= 1
        assert any("retry" in s.lower() or "check" in s.lower() for s in steps)
