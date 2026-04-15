"""FLAN-T5 integration for per-sentence deep analysis.

Implements: FR-T5-02, FR-T5-03, FR-T5-04, FR-T5-05, FR-T5-07
Design: §5
"""

from __future__ import annotations

from phraseturner.t5.context import (
    SentenceContext,
    T5Runner,
    build_context,
    format_context_string,
    truncate_for_t5,
)
from phraseturner.t5.gating import (
    GatingContext,
    count_expected_tasks,
    select_tasks,
)
from phraseturner.t5.prompts import (
    AI_PATTERN_DETECTION,
    ALL_TASKS,
    CORE_MEANING,
    PARAPHRASE_HINTS,
    PERSONA_COMPLIANCE,
    SENTENCE_FUNCTION,
    STYLE_CLASSIFICATION,
    TASK_MAP,
    TONE_ASSESSMENT,
    T5TaskConfig,
    format_prompt,
)
from phraseturner.t5.validation import (
    T5Output,
    parse_persona_compliance_output,
    parse_tone_output,
    validate_and_threshold,
)

__all__ = [
    "AI_PATTERN_DETECTION",
    "ALL_TASKS",
    "CORE_MEANING",
    "PARAPHRASE_HINTS",
    "PERSONA_COMPLIANCE",
    "SENTENCE_FUNCTION",
    "STYLE_CLASSIFICATION",
    "TASK_MAP",
    "TONE_ASSESSMENT",
    "GatingContext",
    "SentenceContext",
    "T5Output",
    "T5Runner",
    "T5TaskConfig",
    "build_context",
    "count_expected_tasks",
    "format_context_string",
    "format_prompt",
    "parse_persona_compliance_output",
    "parse_tone_output",
    "select_tasks",
    "truncate_for_t5",
    "validate_and_threshold",
]
