"""Stage 1 analyzer: Tone metrics.

Compute VADER sentiment scores (per-sentence and overall), contraction
density, and formal marker detection (Latin abbreviations, passive
constructions, nominalizations).

This module is CPU-bound and is called via ``asyncio.to_thread()``
by the pipeline orchestrator (Task 3.10).

Implements §4.3.
Requirements: FR-PIPELINE-06.
"""

from __future__ import annotations

import dataclasses
import re
from typing import Any

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Module-level singleton — created once, reused across calls.
_VADER: SentimentIntensityAnalyzer = SentimentIntensityAnalyzer()

# ---------------------------------------------------------------------------
# Contraction patterns
# ---------------------------------------------------------------------------

_CONTRACTIONS: frozenset[str] = frozenset(
    {
        "don't",
        "can't",
        "won't",
        "i'm",
        "you're",
        "they're",
        "it's",
        "we're",
        "he's",
        "she's",
        "that's",
        "there's",
        "who's",
        "what's",
        "where's",
        "how's",
        "isn't",
        "aren't",
        "wasn't",
        "weren't",
        "hasn't",
        "haven't",
        "hadn't",
        "doesn't",
        "didn't",
        "couldn't",
        "wouldn't",
        "shouldn't",
        "i've",
        "you've",
        "we've",
        "they've",
        "i'll",
        "you'll",
        "he'll",
        "she'll",
        "we'll",
        "they'll",
        "it'll",
        "i'd",
        "you'd",
        "he'd",
        "she'd",
        "we'd",
        "they'd",
        "let's",
        "ain't",
        "mustn't",
        "shan't",
        "needn't",
        "mightn't",
    }
)
"""Common English contractions (lowercased). FR-PIPELINE-06."""

# ---------------------------------------------------------------------------
# Formal marker patterns
# ---------------------------------------------------------------------------

_LATIN_ABBREVIATIONS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\be\.g\.", re.IGNORECASE),
    re.compile(r"\bi\.e\.", re.IGNORECASE),
    re.compile(r"\bviz\.", re.IGNORECASE),
    re.compile(r"\bcf\.", re.IGNORECASE),
    re.compile(r"\bet\s+al\.", re.IGNORECASE),
    re.compile(r"\betc\.", re.IGNORECASE),
    re.compile(r"\bibid\.", re.IGNORECASE),
    re.compile(r"\bsic\b", re.IGNORECASE),
    re.compile(r"\bper\s+se\b", re.IGNORECASE),
    re.compile(r"\bad\s+hoc\b", re.IGNORECASE),
    re.compile(r"\bde\s+facto\b", re.IGNORECASE),
    re.compile(r"\binter\s+alia\b", re.IGNORECASE),
)
"""Compiled regex patterns for Latin abbreviations."""

_NOMINALIZATION_SUFFIXES: tuple[str, ...] = (
    "tion",
    "sion",
    "ment",
    "ness",
    "ity",
    "ance",
    "ence",
)
"""Common nominalization suffixes for formal marker detection."""

_PASSIVE_DEP_LABELS: frozenset[str] = frozenset({"nsubjpass", "auxpass"})
"""spaCy dependency labels indicating passive constructions."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class SentimentScores:
    """VADER sentiment scores for a single text unit.

    Attributes:
        compound: VADER compound score (-1.0 to 1.0).
        positive: Positive proportion (0.0 to 1.0).
        negative: Negative proportion (0.0 to 1.0).
        neutral: Neutral proportion (0.0 to 1.0).
    """

    compound: float
    positive: float
    negative: float
    neutral: float


@dataclasses.dataclass(frozen=True)
class ToneResult:
    """Result of the tone analyzer.

    Attributes:
        per_sentence_sentiment: VADER scores per sentence.
            Implements FR-PIPELINE-06.
        overall_sentiment: VADER scores for the full text.
            Implements FR-PIPELINE-06.
        contraction_density: Contractions / total words.
            Implements FR-PIPELINE-06.
        formal_marker_count: Count of formal markers found.
            Implements FR-PIPELINE-06.
        formal_markers: List of formal markers detected.
            Implements FR-PIPELINE-06.
    """

    per_sentence_sentiment: list[SentimentScores]
    overall_sentiment: SentimentScores
    contraction_density: float
    formal_marker_count: int
    formal_markers: list[str]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _vader_scores(text: str) -> SentimentScores:
    """Compute VADER sentiment scores for *text*.

    Args:
        text: The text to analyse.

    Returns:
        A :class:`SentimentScores` with compound, positive, negative,
        and neutral values.
    """
    scores = _VADER.polarity_scores(text)
    return SentimentScores(
        compound=scores["compound"],
        positive=scores["pos"],
        negative=scores["neg"],
        neutral=scores["neu"],
    )


def _compute_contraction_density(sentences: list[str]) -> float:
    """Compute contraction density (contractions / total words).

    Args:
        sentences: Sentence texts produced by Stage 0.

    Returns:
        Contraction density in range [0.0, 1.0], or 0.0 when there
        are no words.
    """
    total_words = 0
    contraction_count = 0

    for sentence in sentences:
        for word in sentence.split():
            total_words += 1
            if word.lower() in _CONTRACTIONS:
                contraction_count += 1

    if total_words == 0:
        return 0.0

    return contraction_count / total_words


def _detect_latin_abbreviations(text: str) -> list[str]:
    """Detect Latin abbreviations in *text*.

    Args:
        text: The full text to scan.

    Returns:
        List of matched Latin abbreviation strings.
    """
    markers: list[str] = []
    for pattern in _LATIN_ABBREVIATIONS:
        for match in pattern.finditer(text):
            markers.append(match.group())
    return markers


def _detect_passive_constructions(doc: Any) -> list[str]:
    """Detect passive constructions via spaCy dependency labels.

    Args:
        doc: The spaCy ``Doc``.  Returns empty list when ``None``.

    Returns:
        List of passive marker tokens (e.g. ``"nsubjpass:considered"``).
    """
    if doc is None:
        return []

    markers: list[str] = []
    for token in doc:
        if token.dep_ in _PASSIVE_DEP_LABELS:
            markers.append(f"{token.dep_}:{token.text}")
    return markers


def _detect_nominalizations(sentences: list[str]) -> list[str]:
    """Detect nominalizations (words with formal suffixes).

    Only considers words of 6+ characters to avoid false positives
    on short common words (e.g. "once", "dance", "fence").

    Args:
        sentences: Sentence texts produced by Stage 0.

    Returns:
        List of nominalized words found.
    """
    markers: list[str] = []
    seen: set[str] = set()

    for sentence in sentences:
        for word in sentence.split():
            lowered = word.lower().strip(".,;:!?\"'()[]")
            if len(lowered) < 6:  # noqa: PLR2004
                continue
            for suffix in _NOMINALIZATION_SUFFIXES:
                if lowered.endswith(suffix) and lowered not in seen:
                    seen.add(lowered)
                    markers.append(lowered)
                    break

    return markers


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_tone(
    sentences: list[str],
    doc: Any,
) -> ToneResult:
    """Analyse tone of *sentences*. Implements FR-PIPELINE-06.

    Computes VADER sentiment scores (per-sentence and overall),
    contraction density, and formal marker detection (Latin
    abbreviations, passive constructions, nominalizations).

    Args:
        sentences: Sentence texts produced by Stage 0.
        doc: The spaCy ``Doc`` (used for passive voice detection;
            may be ``None`` for Tier 0 fallback).

    Returns:
        A :class:`ToneResult` with all tone metrics.
    """
    # VADER sentiment -- per-sentence and overall
    per_sentence_sentiment = [_vader_scores(s) for s in sentences]
    full_text = " ".join(sentences)
    overall_sentiment = _vader_scores(full_text)

    # Contraction density
    contraction_density = _compute_contraction_density(sentences)

    # Formal markers
    latin_markers = _detect_latin_abbreviations(full_text)
    passive_markers = _detect_passive_constructions(doc)
    nominalization_markers = _detect_nominalizations(sentences)

    all_markers = latin_markers + passive_markers + nominalization_markers

    return ToneResult(
        per_sentence_sentiment=per_sentence_sentiment,
        overall_sentiment=overall_sentiment,
        contraction_density=contraction_density,
        formal_marker_count=len(all_markers),
        formal_markers=all_markers,
    )
