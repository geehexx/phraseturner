"""Tests for FLAN-T5 task gating logic.

Validates: FR-T5-03 (AC-FR-T5-03.1 through AC-FR-T5-03.4)
Design: §5.4
"""

from __future__ import annotations

from phraseturner.t5.gating import GatingContext, count_expected_tasks, select_tasks
from phraseturner.t5.prompts import (
    AI_PATTERN_DETECTION,
    CORE_MEANING,
    PARAPHRASE_HINTS,
    PERSONA_COMPLIANCE,
    SENTENCE_FUNCTION,
    STYLE_CLASSIFICATION,
    TONE_ASSESSMENT,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ALWAYS_NAMES = {
    "style_classification",
    "core_meaning",
    "sentence_function",
    "tone_assessment",
}
"""Names of the 4 tasks that must always be present."""


def _task_names(tasks: list) -> set[str]:
    return {t.name for t in tasks}


# ---------------------------------------------------------------------------
# Always-run tasks
# ---------------------------------------------------------------------------


class TestAlwaysRunTasks:
    """Verify the 4 always-run tasks are present in every context."""

    def test_minimal_context_includes_always_tasks(self) -> None:
        ctx = GatingContext(
            ai_signal="likely-human",
            include_suggestions=False,
            has_persona=False,
        )
        tasks = select_tasks(ctx)
        assert _ALWAYS_NAMES.issubset(_task_names(tasks))

    def test_always_tasks_count_is_four(self) -> None:
        ctx = GatingContext(
            ai_signal="uncertain",
            include_suggestions=False,
            has_persona=False,
        )
        tasks = select_tasks(ctx)
        assert len(tasks) == 4

    def test_always_tasks_order_is_deterministic(self) -> None:
        ctx = GatingContext(
            ai_signal="likely-human",
            include_suggestions=False,
            has_persona=False,
        )
        first = select_tasks(ctx)
        second = select_tasks(ctx)
        assert first == second

    def test_always_tasks_are_correct_objects(self) -> None:
        ctx = GatingContext(
            ai_signal="likely-human",
            include_suggestions=False,
            has_persona=False,
        )
        tasks = select_tasks(ctx)
        assert tasks[0] is STYLE_CLASSIFICATION
        assert tasks[1] is CORE_MEANING
        assert tasks[2] is SENTENCE_FUNCTION
        assert tasks[3] is TONE_ASSESSMENT


# ---------------------------------------------------------------------------
# Conditional: AI pattern detection - AC-FR-T5-03.1
# ---------------------------------------------------------------------------


class TestAIPatternGating:
    """AC-FR-T5-03.1: AI pattern detection only when ai_signal == 'likely-ai'."""

    def test_included_when_likely_ai(self) -> None:
        ctx = GatingContext(
            ai_signal="likely-ai",
            include_suggestions=False,
            has_persona=False,
        )
        tasks = select_tasks(ctx)
        assert AI_PATTERN_DETECTION in tasks

    def test_excluded_when_likely_human(self) -> None:
        ctx = GatingContext(
            ai_signal="likely-human",
            include_suggestions=False,
            has_persona=False,
        )
        tasks = select_tasks(ctx)
        assert AI_PATTERN_DETECTION not in tasks

    def test_excluded_when_uncertain(self) -> None:
        ctx = GatingContext(
            ai_signal="uncertain",
            include_suggestions=False,
            has_persona=False,
        )
        tasks = select_tasks(ctx)
        assert AI_PATTERN_DETECTION not in tasks


# ---------------------------------------------------------------------------
# Conditional: Paraphrase hints - AC-FR-T5-03.2
# ---------------------------------------------------------------------------


class TestParaphraseHintsGating:
    """AC-FR-T5-03.2: Paraphrase hints only when include_suggestions=true."""

    def test_included_when_suggestions_requested(self) -> None:
        ctx = GatingContext(
            ai_signal="likely-human",
            include_suggestions=True,
            has_persona=False,
        )
        tasks = select_tasks(ctx)
        assert PARAPHRASE_HINTS in tasks

    def test_excluded_when_suggestions_not_requested(self) -> None:
        ctx = GatingContext(
            ai_signal="likely-human",
            include_suggestions=False,
            has_persona=False,
        )
        tasks = select_tasks(ctx)
        assert PARAPHRASE_HINTS not in tasks


# ---------------------------------------------------------------------------
# Conditional: Persona compliance - AC-FR-T5-03.3
# ---------------------------------------------------------------------------


class TestPersonaComplianceGating:
    """AC-FR-T5-03.3: Persona compliance only when persona provided."""

    def test_included_when_persona_provided(self) -> None:
        ctx = GatingContext(
            ai_signal="likely-human",
            include_suggestions=False,
            has_persona=True,
        )
        tasks = select_tasks(ctx)
        assert PERSONA_COMPLIANCE in tasks

    def test_excluded_when_no_persona(self) -> None:
        ctx = GatingContext(
            ai_signal="likely-human",
            include_suggestions=False,
            has_persona=False,
        )
        tasks = select_tasks(ctx)
        assert PERSONA_COMPLIANCE not in tasks


# ---------------------------------------------------------------------------
# All conditionals active - AC-FR-T5-03.4
# ---------------------------------------------------------------------------


class TestFullGating:
    """AC-FR-T5-03.4: All 7 tasks when all conditions met."""

    def test_all_conditionals_active(self) -> None:
        ctx = GatingContext(
            ai_signal="likely-ai",
            include_suggestions=True,
            has_persona=True,
        )
        tasks = select_tasks(ctx)
        assert len(tasks) == 7
        names = _task_names(tasks)
        assert names == {
            "style_classification",
            "core_meaning",
            "sentence_function",
            "tone_assessment",
            "ai_pattern_detection",
            "paraphrase_hints",
            "persona_compliance",
        }

    def test_reduces_to_four_when_no_conditionals(self) -> None:
        """AC-FR-T5-03.4: 7->3-4 calls - minimum is 4."""
        ctx = GatingContext(
            ai_signal="likely-human",
            include_suggestions=False,
            has_persona=False,
        )
        tasks = select_tasks(ctx)
        assert len(tasks) == 4


# ---------------------------------------------------------------------------
# count_expected_tasks consistency
# ---------------------------------------------------------------------------


class TestCountExpectedTasks:
    """Verify count_expected_tasks matches len(select_tasks)."""

    def test_count_matches_select_minimal(self) -> None:
        ctx = GatingContext(
            ai_signal="likely-human",
            include_suggestions=False,
            has_persona=False,
        )
        assert count_expected_tasks(ctx) == len(select_tasks(ctx))

    def test_count_matches_select_all(self) -> None:
        ctx = GatingContext(
            ai_signal="likely-ai",
            include_suggestions=True,
            has_persona=True,
        )
        assert count_expected_tasks(ctx) == len(select_tasks(ctx))

    def test_count_matches_select_partial(self) -> None:
        ctx = GatingContext(
            ai_signal="likely-ai",
            include_suggestions=False,
            has_persona=True,
        )
        assert count_expected_tasks(ctx) == len(select_tasks(ctx))


# ---------------------------------------------------------------------------
# GatingContext dataclass
# ---------------------------------------------------------------------------


class TestGatingContext:
    """Verify GatingContext is frozen and has slots."""

    def test_frozen(self) -> None:
        ctx = GatingContext(
            ai_signal="likely-human",
            include_suggestions=False,
            has_persona=False,
        )
        try:
            ctx.ai_signal = "likely-ai"  # type: ignore[misc]
            msg = "Should have raised FrozenInstanceError"
            raise AssertionError(msg)
        except AttributeError:
            pass

    def test_equality(self) -> None:
        a = GatingContext(
            ai_signal="likely-ai", include_suggestions=True, has_persona=False,
        )
        b = GatingContext(
            ai_signal="likely-ai", include_suggestions=True, has_persona=False,
        )
        assert a == b

    def test_inequality(self) -> None:
        a = GatingContext(
            ai_signal="likely-ai", include_suggestions=True, has_persona=False,
        )
        b = GatingContext(
            ai_signal="likely-human", include_suggestions=True, has_persona=False,
        )
        assert a != b
