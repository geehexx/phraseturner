"""Stage 1 analyzer: Vocabulary metrics.

Compute MTLD (Measure of Textual Lexical Diversity), TTR (Type-Token
Ratio), and passive voice ratio via spaCy dependency parsing.

This module is CPU-bound and is called via ``asyncio.to_thread()``
by the pipeline orchestrator (Task 3.10).

Implements §4.3.
Requirements: FR-PIPELINE-05.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any

from lexicalrichness import LexicalRichness


@dataclasses.dataclass(frozen=True)
class VocabularyResult:
    """Result of the vocabulary analyzer.

    Attributes:
        mtld: Measure of Textual Lexical Diversity.  A length-independent
            vocabulary richness metric.  Returns 0.0 for texts too short
            for MTLD computation.
            Implements AC-FR-PIPELINE-05.1.
        ttr: Type-Token Ratio — unique words / total words (lowercased,
            alphabetic tokens only).  Range (0.0, 1.0] for non-empty
            text; 0.0 when no alphabetic words are present.
            Implements AC-FR-PIPELINE-05.2.
        passive_voice_ratio: Passive voice constructions / total
            sentences, detected via spaCy dependency labels ``nsubjpass``
            and ``auxpass``.  Returns 0.0 when *doc* is ``None``
            (Tier 0 fallback).
            Implements AC-FR-PIPELINE-05.3.
    """

    mtld: float
    ttr: float
    passive_voice_ratio: float


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compute_mtld(sentences: list[str]) -> float:
    """Compute MTLD via the ``lexicalrichness`` library.

    Args:
        sentences: Sentence texts produced by Stage 0.

    Returns:
        MTLD score, or 0.0 if the text is too short for computation.
        Implements AC-FR-PIPELINE-05.1.
    """
    text = " ".join(sentences)
    if not text.strip():
        return 0.0

    try:
        lr = LexicalRichness(text)
        # LexicalRichness requires a minimum number of words
        if lr.words < 10:  # noqa: PLR2004
            return 0.0
        result: float = lr.mtld()
        # Guard against inf/nan from degenerate inputs
        if not isinstance(result, (int, float)) or math.isnan(result) or math.isinf(result):
            return 0.0
        return float(result)
    except (ValueError, ZeroDivisionError):
        # lexicalrichness raises on very short or degenerate texts
        return 0.0


def _compute_ttr(sentences: list[str]) -> float:
    """Compute Type-Token Ratio (unique words / total words).

    Only lowercased alphabetic tokens are considered.

    Args:
        sentences: Sentence texts produced by Stage 0.

    Returns:
        TTR in range (0.0, 1.0] for non-empty text, or 0.0 when no
        alphabetic words are present.
        Implements AC-FR-PIPELINE-05.2, P-inv-10.
    """
    total = 0
    unique: set[str] = set()

    for sentence in sentences:
        for word in sentence.split():
            lowered = word.lower()
            # Only count alphabetic tokens
            if lowered.isalpha():
                total += 1
                unique.add(lowered)

    if total == 0:
        return 0.0

    return len(unique) / total


def _compute_passive_voice_ratio(
    sentences: list[str],
    doc: Any,
) -> float:
    """Compute passive voice ratio via spaCy dependency parsing.

    A sentence is considered passive if it contains a token with
    dependency label ``nsubjpass`` or ``auxpass`` (spaCy's labels for
    passive constructions).

    Args:
        sentences: Sentence texts produced by Stage 0.
        doc: The spaCy ``Doc``.  When ``None`` (Tier 0), returns 0.0.

    Returns:
        Passive constructions / total sentences, or 0.0 when *doc* is
        ``None`` or there are no sentences.
        Implements AC-FR-PIPELINE-05.3.
    """
    if doc is None or not sentences:
        return 0.0

    passive_labels = {"nsubjpass", "auxpass"}
    passive_count = 0

    for sent in doc.sents:
        for token in sent:
            if token.dep_ in passive_labels:
                passive_count += 1
                break  # One passive marker is enough per sentence

    return passive_count / len(sentences)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_vocabulary(
    sentences: list[str],
    doc: Any,
) -> VocabularyResult:
    """Analyse vocabulary of *sentences*. Implements FR-PIPELINE-05.

    Computes MTLD (lexical diversity), TTR (type-token ratio), and
    passive voice ratio (via spaCy dependency parsing).

    Args:
        sentences: Sentence texts produced by Stage 0.
        doc: The spaCy ``Doc`` (used for passive voice detection;
            may be ``None`` for Tier 0 fallback).

    Returns:
        A :class:`VocabularyResult` with all vocabulary metrics.
    """
    return VocabularyResult(
        mtld=_compute_mtld(sentences),
        ttr=_compute_ttr(sentences),
        passive_voice_ratio=_compute_passive_voice_ratio(sentences, doc),
    )
