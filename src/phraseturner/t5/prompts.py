"""FLAN-T5 prompt templates for 7 per-sentence analysis tasks.

Implements: AC-FR-T5-02.1 through AC-FR-T5-02.3
Design: §5.2

Each task is defined as a ``T5TaskConfig`` dataclass containing the prompt
template, output constraints, confidence threshold, valid labels, fallback
value, and decoding strategy.  Classification tasks use beam search
(``num_beams=4``) for confidence scoring; free-form tasks use greedy
decoding for deterministic output.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class T5TaskConfig:
    """Configuration for a single FLAN-T5 analysis task.

    Attributes:
        name: Machine-readable task identifier.
        prompt_template: Template string with ``{sentence}`` and optional
            ``{context}`` placeholders.
        max_tokens: Maximum output tokens for generation.
        threshold: Confidence threshold for classification tasks.
            ``None`` for free-form tasks (paraphrase hints, core meaning).
        valid_labels: Fixed label set for classification validation.
            ``None`` for free-form tasks.
        fallback: Default label when confidence is below *threshold* or
            output is invalid.  ``None`` for free-form tasks.
        use_beam_search: Whether to use beam search (``num_beams=4``) for
            confidence scoring.  ``False`` selects greedy decoding.
    """

    name: str
    prompt_template: str
    max_tokens: int
    threshold: float | None = None
    valid_labels: list[str] | None = None
    fallback: str | None = None
    use_beam_search: bool = False


# ---------------------------------------------------------------------------
# 7 task configs — AC-FR-T5-02.1, Design §5.2
# ---------------------------------------------------------------------------

STYLE_CLASSIFICATION = T5TaskConfig(
    name="style_classification",
    prompt_template=(
        "Classify the writing style of this sentence as formal, informal, or neutral: {sentence}"
    ),
    max_tokens=8,
    threshold=0.65,
    valid_labels=["formal", "informal", "neutral"],
    fallback="neutral",
    use_beam_search=True,
)
"""Style classification — formal/informal/neutral (threshold 0.65)."""

AI_PATTERN_DETECTION = T5TaskConfig(
    name="ai_pattern_detection",
    prompt_template=(
        "Identify the AI writing pattern in this sentence. Choose one:"
        " formulaic-transition, list-heavy, hedge-stacking,"
        " over-qualification, filler-phrase, repetitive-structure,"
        " none-obvious: {sentence}"
    ),
    max_tokens=8,
    threshold=0.55,
    valid_labels=[
        "formulaic-transition",
        "list-heavy",
        "hedge-stacking",
        "over-qualification",
        "filler-phrase",
        "repetitive-structure",
        "none-obvious",
    ],
    fallback="none-obvious",
    use_beam_search=True,
)
"""AI pattern detection — 7 labels (threshold 0.55)."""

PARAPHRASE_HINTS = T5TaskConfig(
    name="paraphrase_hints",
    prompt_template=(
        "Suggest a brief directive for improving this sentence (do not rewrite it): {sentence}"
    ),
    max_tokens=20,
    threshold=None,
    valid_labels=None,
    fallback=None,
    use_beam_search=False,
)
"""Paraphrase hints — free-form directive phrase."""

CORE_MEANING = T5TaskConfig(
    name="core_meaning",
    prompt_template=("Extract the core meaning of this sentence in 10 words or fewer: {sentence}"),
    max_tokens=15,
    threshold=None,
    valid_labels=None,
    fallback=None,
    use_beam_search=False,
)
"""Core meaning extraction — ≤10 words, free-form."""

SENTENCE_FUNCTION = T5TaskConfig(
    name="sentence_function",
    prompt_template=(
        "Classify the function of this sentence. Choose one:"
        " claim, evidence, background, transition, conclusion: {sentence}"
    ),
    max_tokens=8,
    threshold=0.60,
    valid_labels=["claim", "evidence", "background", "transition", "conclusion"],
    fallback="background",
    use_beam_search=True,
)
"""Sentence function — 5 labels (threshold 0.60)."""

TONE_ASSESSMENT = T5TaskConfig(
    name="tone_assessment",
    prompt_template=(
        "Assess the tone of this sentence on three dimensions"
        " (formality, confidence, directness) as low, medium, or high:"
        " {sentence}"
    ),
    max_tokens=20,
    threshold=0.60,
    valid_labels=["low", "medium", "high"],
    fallback="medium",
    use_beam_search=True,
)
"""Tone assessment — 3x low/medium/high (threshold 0.60/dim)."""

PERSONA_COMPLIANCE = T5TaskConfig(
    name="persona_compliance",
    prompt_template=(
        "Given the persona tone targets ({context}), classify this"
        " sentence's compliance as compliant, minor-violation, or"
        " major-violation, and briefly state the issue: {sentence}"
    ),
    max_tokens=25,
    threshold=0.65,
    valid_labels=["compliant", "minor-violation", "major-violation"],
    fallback="compliant",
    use_beam_search=True,
)
"""Persona compliance — 3 labels + issue (threshold 0.65)."""


# ---------------------------------------------------------------------------
# Aggregate collections
# ---------------------------------------------------------------------------

ALL_TASKS: list[T5TaskConfig] = [
    STYLE_CLASSIFICATION,
    AI_PATTERN_DETECTION,
    PARAPHRASE_HINTS,
    CORE_MEANING,
    SENTENCE_FUNCTION,
    TONE_ASSESSMENT,
    PERSONA_COMPLIANCE,
]
"""All 7 T5 task configurations."""

TASK_MAP: dict[str, T5TaskConfig] = {task.name: task for task in ALL_TASKS}
"""Mapping from task name to its configuration."""


# ---------------------------------------------------------------------------
# Prompt formatting — AC-FR-T5-02.1
# ---------------------------------------------------------------------------


def format_prompt(
    task: T5TaskConfig,
    sentence: str,
    context: str | None = None,
) -> str:
    """Fill template placeholders to produce a ready-to-infer prompt.

    Args:
        task: The task configuration whose template to fill.
        sentence: The sentence text to analyse.
        context: Optional context string (e.g. persona tone targets).
            Required for tasks whose template contains ``{context}``.

    Returns:
        The formatted prompt string ready for FLAN-T5 inference.

    Raises:
        ValueError: If the template contains ``{context}`` but *context*
            is ``None``.
    """
    if "{context}" in task.prompt_template and context is None:
        msg = f"Task '{task.name}' requires a context argument but None was provided"
        raise ValueError(msg)

    return task.prompt_template.format(
        sentence=sentence,
        context=context or "",
    )
