"""Confidence thresholding and label validation for FLAN-T5 outputs.

Validates T5 classification outputs against fixed label sets and applies
per-task confidence thresholds.  Below-threshold or invalid outputs fall
back to the task's default label with ``confidence=0.0``.

Implements: AC-FR-T5-04.1 through AC-FR-T5-04.3
Design: §5.5
Requirements: FR-T5-04
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from phraseturner.t5.prompts import T5TaskConfig


@dataclass(frozen=True, slots=True)
class T5Output:
    """Result of validating and thresholding a single T5 output.

    Attributes:
        label: The output label or free-form text.
        confidence: Confidence score in the range 0.0-1.0.
        is_fallback: Whether this result was produced by a fallback
            (invalid label, below-threshold confidence, or missing output).
    """

    label: str
    confidence: float
    is_fallback: bool


def validate_and_threshold(
    raw_output: str,
    confidence: float,
    task: T5TaskConfig,
) -> T5Output:
    """Validate a raw T5 output against its task config and apply thresholding.

    For free-form tasks (no ``valid_labels``), the output is returned as-is
    with the given confidence.  For classification tasks, the output is
    normalised (lowercased, stripped) and checked against the fixed label
    set.  Invalid labels or below-threshold confidence trigger a fallback.

    Implements FR-T5-04.

    Args:
        raw_output: Raw text output from FLAN-T5 inference.
        confidence: Beam-search softmax confidence score (0.0-1.0).
        task: The task configuration defining labels, threshold, and
            fallback.

    Returns:
        A ``T5Output`` with the validated label, confidence, and fallback
        flag.
    """
    # Free-form tasks (paraphrase_hints, core_meaning) -- no label validation.
    if task.valid_labels is None:
        return T5Output(
            label=raw_output.strip(),
            confidence=confidence,
            is_fallback=False,
        )

    normalised = raw_output.strip().lower()

    # Invalid label -> fallback.
    if normalised not in task.valid_labels:
        return T5Output(
            label=task.fallback or "",
            confidence=0.0,
            is_fallback=True,
        )

    # Below threshold -> fallback.  AC-FR-T5-04.3
    if task.threshold is not None and confidence < task.threshold:
        return T5Output(
            label=task.fallback or "",
            confidence=0.0,
            is_fallback=True,
        )

    # Valid label, sufficient confidence.
    return T5Output(
        label=normalised,
        confidence=confidence,
        is_fallback=False,
    )


# ---------------------------------------------------------------------------
# Tone assessment parser -- multi-dimension output
# ---------------------------------------------------------------------------

_TONE_VALID_LABELS: list[str] = ["low", "medium", "high"]
_TONE_FALLBACK: str = "medium"

# Matches patterns like "formality: high" with flexible whitespace/punctuation.
_DIMENSION_PATTERN: re.Pattern[str] = re.compile(
    r"(\w+)\s*[:=]\s*(\w+)",
)


def parse_tone_output(
    raw_output: str,
    confidence: float,
    threshold: float = 0.60,
) -> dict[str, T5Output]:
    """Parse and validate multi-dimension tone assessment output.

    Tone assessment produces output like
    ``"formality: high, confidence: medium, directness: low"``.
    Each dimension is independently validated against ``["low", "medium",
    "high"]`` and thresholded.

    Implements FR-T5-04 (tone assessment, threshold 0.60/dim).

    Args:
        raw_output: Raw tone assessment string from FLAN-T5.
        confidence: Overall beam-search softmax confidence score.
        threshold: Per-dimension confidence threshold (default 0.60).

    Returns:
        Dict mapping dimension name to its validated ``T5Output``.
        Unrecognised dimensions are included with fallback values.
    """
    results: dict[str, T5Output] = {}

    for match in _DIMENSION_PATTERN.finditer(raw_output):
        dimension = match.group(1).lower()
        value = match.group(2).lower()

        if value in _TONE_VALID_LABELS and confidence >= threshold:
            results[dimension] = T5Output(
                label=value,
                confidence=confidence,
                is_fallback=False,
            )
        else:
            results[dimension] = T5Output(
                label=_TONE_FALLBACK,
                confidence=0.0,
                is_fallback=True,
            )

    # If no dimensions were parsed, return empty dict -- caller handles.
    return results


# ---------------------------------------------------------------------------
# Persona compliance parser -- label + issue extraction
# ---------------------------------------------------------------------------

_COMPLIANCE_VALID_LABELS: list[str] = [
    "compliant",
    "minor-violation",
    "major-violation",
]
_COMPLIANCE_FALLBACK: str = "compliant"

# Matches "label: issue description" or just "label".
_COMPLIANCE_PATTERN: re.Pattern[str] = re.compile(
    r"^\s*([\w-]+)\s*(?:[:]\s*(.+))?\s*$",
    re.DOTALL,
)


def parse_persona_compliance_output(
    raw_output: str,
    confidence: float,
    threshold: float = 0.65,
) -> tuple[T5Output, str | None]:
    """Parse and validate persona compliance output.

    Persona compliance produces output like
    ``"major-violation: formal register in casual persona"`` or simply
    ``"compliant"``.  The label is validated against the fixed set and
    thresholded; the issue description (if present) is extracted.

    Implements FR-T5-04 (persona compliance, threshold 0.65).

    Args:
        raw_output: Raw persona compliance string from FLAN-T5.
        confidence: Beam-search softmax confidence score.
        threshold: Confidence threshold (default 0.65).

    Returns:
        Tuple of (validated ``T5Output`` for the label, issue string or
        ``None``).
    """
    match = _COMPLIANCE_PATTERN.match(raw_output.strip())

    if match is None:
        return (
            T5Output(
                label=_COMPLIANCE_FALLBACK,
                confidence=0.0,
                is_fallback=True,
            ),
            None,
        )

    label = match.group(1).lower()
    issue = match.group(2)
    if issue is not None:
        issue = issue.strip() or None

    # Invalid label -> fallback.
    if label not in _COMPLIANCE_VALID_LABELS:
        return (
            T5Output(
                label=_COMPLIANCE_FALLBACK,
                confidence=0.0,
                is_fallback=True,
            ),
            None,
        )

    # Below threshold -> fallback.
    if confidence < threshold:
        return (
            T5Output(
                label=_COMPLIANCE_FALLBACK,
                confidence=0.0,
                is_fallback=True,
            ),
            None,
        )

    # Valid label, sufficient confidence.
    return (
        T5Output(
            label=label,
            confidence=confidence,
            is_fallback=False,
        ),
        issue,
    )
