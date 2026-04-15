"""Stage 1 analyzer: Readability metrics.

Compute consensus grade (arithmetic mean of 7 readability formulas),
Flesch Reading Ease score, and per-sentence readability grades via
the ``textstat`` library.

This module is CPU-bound and is called via ``asyncio.to_thread()``
by the pipeline orchestrator (Task 3.10).

Implements S4.3.
Requirements: FR-PIPELINE-03.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import textstat

_FORMULA_NAMES: tuple[str, ...] = (
    "flesch_kincaid_grade",
    "gunning_fog",
    "coleman_liau_index",
    "smog_index",
    "automated_readability_index",
    "dale_chall_readability_score",
    "linsear_write_formula",
)
"""The 7 readability formulas used for the consensus grade (S4.3)."""


@dataclasses.dataclass(frozen=True)
class ReadabilityResult:
    """Result of the readability analyzer.

    Attributes:
        consensus_grade: Arithmetic mean of the 7 readability formula
            grades.  Implements AC-FR-PIPELINE-03.1.
        flesch_reading_ease: Flesch Reading Ease score on a 0-100 scale.
            Implements AC-FR-PIPELINE-03.2.
        per_sentence_grades: Consensus grade computed independently for
            each sentence.
        individual_grades: Mapping of formula name to its grade for the
            full text.
    """

    consensus_grade: float
    flesch_reading_ease: float
    per_sentence_grades: list[float]
    individual_grades: dict[str, float]


def _compute_grades(text: str) -> dict[str, float]:
    """Compute all 7 readability formula grades for *text*.

    Args:
        text: The text to analyse.

    Returns:
        Mapping of formula name to grade value.
    """
    return {
        name: float(getattr(textstat, name)(text))
        for name in _FORMULA_NAMES
    }


def _consensus(grades: dict[str, float]) -> float:
    """Return the arithmetic mean of the grade values.

    Args:
        grades: Mapping of formula name to grade value.

    Returns:
        Arithmetic mean rounded to 1 decimal place.
        Returns ``0.0`` when *grades* is empty.
    """
    if not grades:
        return 0.0
    return round(sum(grades.values()) / len(grades), 1)


def analyze_readability(
    sentences: list[str],
    doc: Any,
) -> ReadabilityResult:
    """Analyse readability of *sentences*. Implements FR-PIPELINE-03.

    Computes the consensus grade (arithmetic mean of 7 formulas),
    Flesch Reading Ease, and per-sentence consensus grades using the
    ``textstat`` library (AC-FR-PIPELINE-03.3).

    The *doc* parameter is unused by this analyzer but present for a
    uniform Stage 1 analyzer signature.

    Args:
        sentences: Sentence texts produced by Stage 0.
        doc: The spaCy ``Doc`` (unused by this analyzer).

    Returns:
        A :class:`ReadabilityResult` with full-text and per-sentence
        metrics.
    """
    _ = doc  # Unused; uniform Stage 1 signature.
    full_text = " ".join(sentences)

    # Full-text grades -- AC-FR-PIPELINE-03.1
    individual_grades = _compute_grades(full_text)
    consensus_grade = _consensus(individual_grades)

    # Flesch Reading Ease -- AC-FR-PIPELINE-03.2
    flesch_reading_ease = float(textstat.flesch_reading_ease(full_text))

    # Per-sentence consensus grades
    per_sentence_grades = [
        _consensus(_compute_grades(sentence)) for sentence in sentences
    ]

    return ReadabilityResult(
        consensus_grade=consensus_grade,
        flesch_reading_ease=flesch_reading_ease,
        per_sentence_grades=per_sentence_grades,
        individual_grades=individual_grades,
    )
