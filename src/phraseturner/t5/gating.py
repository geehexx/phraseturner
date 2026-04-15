"""Task gating logic for FLAN-T5 per-sentence analysis.

Reduces T5 inference calls from 7 to 3-4 per sentence by running only
relevant tasks based on the analysis context.

Implements: AC-FR-T5-03.1 through AC-FR-T5-03.4
Design: §5.4
"""

from __future__ import annotations

from dataclasses import dataclass

from phraseturner.t5.prompts import (
    AI_PATTERN_DETECTION,
    CORE_MEANING,
    PARAPHRASE_HINTS,
    PERSONA_COMPLIANCE,
    SENTENCE_FUNCTION,
    STYLE_CLASSIFICATION,
    TONE_ASSESSMENT,
    T5TaskConfig,
)

# ---------------------------------------------------------------------------
# Always-run tasks — these fire for every sentence regardless of context.
# ---------------------------------------------------------------------------

_ALWAYS_TASKS: list[T5TaskConfig] = [
    STYLE_CLASSIFICATION,
    CORE_MEANING,
    SENTENCE_FUNCTION,
    TONE_ASSESSMENT,
]
"""4 tasks that always run. Implements FR-T5-03."""


@dataclass(frozen=True, slots=True)
class GatingContext:
    """Context signals that determine which T5 tasks to run.

    Attributes:
        ai_signal: AI detection result — ``"likely-ai"``,
            ``"likely-human"``, or ``"uncertain"``.
        include_suggestions: Whether the caller requested paraphrase
            suggestions via ``include_suggestions=true``.
        has_persona: Whether a persona was provided for the analysis.
    """

    ai_signal: str
    include_suggestions: bool
    has_persona: bool


def select_tasks(context: GatingContext) -> list[T5TaskConfig]:
    """Select T5 tasks to run based on the analysis context.

    Always includes style classification, core meaning extraction,
    sentence function, and tone assessment (4 tasks).  Conditionally
    adds AI pattern detection, paraphrase hints, and persona compliance
    based on the gating context.  Implements FR-T5-03.

    Args:
        context: Gating signals from the analysis pipeline.

    Returns:
        Deterministic list of task configs to execute, in a fixed order.
    """
    tasks: list[T5TaskConfig] = list(_ALWAYS_TASKS)

    # AC-FR-T5-03.1: AI pattern detection only when likely-ai
    if context.ai_signal == "likely-ai":
        tasks.append(AI_PATTERN_DETECTION)

    # AC-FR-T5-03.2: Paraphrase hints only when suggestions requested
    if context.include_suggestions:
        tasks.append(PARAPHRASE_HINTS)

    # AC-FR-T5-03.3: Persona compliance only when persona provided
    if context.has_persona:
        tasks.append(PERSONA_COMPLIANCE)

    return tasks


def count_expected_tasks(context: GatingContext) -> int:
    """Return the number of T5 tasks that would be selected.

    Useful for logging and metrics without materialising the full list.
    Implements FR-T5-03.

    Args:
        context: Gating signals from the analysis pipeline.

    Returns:
        Count of tasks that ``select_tasks`` would return.
    """
    count = len(_ALWAYS_TASKS)
    if context.ai_signal == "likely-ai":
        count += 1
    if context.include_suggestions:
        count += 1
    if context.has_persona:
        count += 1
    return count
