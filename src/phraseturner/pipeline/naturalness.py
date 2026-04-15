"""Stage 1 analyzer: Naturalness metrics.

Compute burstiness (coefficient of variation of sentence lengths),
length skewness, hapax legomena ratio, Zipf R² conformity,
punctuation entropy, and sentence starter diversity.

This module is CPU-bound and is called via ``asyncio.to_thread()``
by the pipeline orchestrator (Task 3.10).

Implements §4.3.
Requirements: FR-PIPELINE-04.
"""

from __future__ import annotations

import dataclasses
import math
import string
from collections import Counter
from typing import Any

import numpy as np
from scipy.stats import skew as scipy_skew

_MIN_SENTENCES_FOR_SKEWNESS: int = 3
"""Minimum number of sentences required to compute skewness."""

_PUNCTUATION_SET: frozenset[str] = frozenset(string.punctuation)
"""Set of ASCII punctuation characters used for entropy calculation."""


@dataclasses.dataclass(frozen=True)
class NaturalnessResult:
    """Result of the naturalness analyzer.

    Attributes:
        burstiness: Coefficient of variation (std/mean) of sentence
            lengths in tokens.  Always ≥ 0.
            Implements AC-FR-PIPELINE-04.1.
        length_skewness: Skewness of the sentence length distribution.
            Implements AC-FR-PIPELINE-04.2.
        hapax_ratio: Words appearing exactly once / total unique words.
            Implements AC-FR-PIPELINE-04.3.
        zipf_r_squared: R² of log-rank vs log-frequency linear
            regression.  Implements AC-FR-PIPELINE-04.4.
        punctuation_entropy: Shannon entropy of the punctuation
            character distribution.  Implements AC-FR-PIPELINE-04.5.
        starter_diversity: Unique first-word lemmas / total sentences.
            Implements AC-FR-PIPELINE-04.6.
    """

    burstiness: float
    length_skewness: float
    hapax_ratio: float
    zipf_r_squared: float
    punctuation_entropy: float
    starter_diversity: float


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sentence_lengths(sentences: list[str]) -> list[int]:
    """Return token counts per sentence via whitespace splitting."""
    return [len(s.split()) for s in sentences]


def _compute_burstiness(lengths: list[int]) -> float:
    """Coefficient of variation (std / mean) of sentence lengths.

    Returns 0.0 when the mean is zero (no tokens).
    Implements AC-FR-PIPELINE-04.1, P-inv-09.
    """
    if not lengths:
        return 0.0
    arr = np.asarray(lengths, dtype=np.float64)
    mean = float(arr.mean())
    if mean == 0.0:
        return 0.0
    return float(arr.std(ddof=0) / mean)


def _compute_length_skewness(lengths: list[int]) -> float:
    """Skewness of sentence length distribution via scipy.

    Returns 0.0 when fewer than 3 sentences (skewness undefined).
    Implements AC-FR-PIPELINE-04.2.
    """
    if len(lengths) < _MIN_SENTENCES_FOR_SKEWNESS:
        return 0.0
    arr = np.asarray(lengths, dtype=np.float64)
    result = float(scipy_skew(arr, bias=True))
    # scipy returns nan for constant arrays (zero variance)
    if math.isnan(result):
        return 0.0
    return result


def _compute_hapax_ratio(sentences: list[str]) -> float:
    """Hapax legomena ratio: words appearing once / total unique words.

    Returns 0.0 when there are no words.
    Implements AC-FR-PIPELINE-04.3.
    """
    word_counts: Counter[str] = Counter()
    for sentence in sentences:
        for word in sentence.split():
            word_counts[word.lower()] += 1

    unique_count = len(word_counts)
    if unique_count == 0:
        return 0.0

    hapax_count = sum(1 for count in word_counts.values() if count == 1)
    return hapax_count / unique_count


def _compute_zipf_r_squared(sentences: list[str]) -> float:
    """R² of log-rank vs log-frequency linear regression (Zipf's law).

    Returns 1.0 for a single unique word (perfect fit by definition).
    Returns 0.0 when there are no words.
    Implements AC-FR-PIPELINE-04.4.
    """
    word_counts: Counter[str] = Counter()
    for sentence in sentences:
        for word in sentence.split():
            word_counts[word.lower()] += 1

    if not word_counts:
        return 0.0

    frequencies = sorted(word_counts.values(), reverse=True)

    if len(frequencies) == 1:
        return 1.0

    ranks = np.arange(1, len(frequencies) + 1, dtype=np.float64)
    freqs = np.asarray(frequencies, dtype=np.float64)

    log_ranks = np.log(ranks)
    log_freqs = np.log(freqs)

    # Linear regression via numpy polyfit (degree 1)
    coeffs = np.polyfit(log_ranks, log_freqs, 1)
    predicted = np.polyval(coeffs, log_ranks)

    ss_res = float(np.sum((log_freqs - predicted) ** 2))
    ss_tot = float(np.sum((log_freqs - log_freqs.mean()) ** 2))

    if ss_tot == 0.0:
        return 1.0

    return 1.0 - (ss_res / ss_tot)


def _compute_punctuation_entropy(sentences: list[str]) -> float:
    """Shannon entropy of punctuation character distribution.

    Returns 0.0 when no punctuation is present.
    Implements AC-FR-PIPELINE-04.5.
    """
    full_text = " ".join(sentences)
    punct_counts: Counter[str] = Counter()
    for char in full_text:
        if char in _PUNCTUATION_SET:
            punct_counts[char] += 1

    total = sum(punct_counts.values())
    if total == 0:
        return 0.0

    entropy = 0.0
    for count in punct_counts.values():
        p = count / total
        entropy -= p * math.log2(p)

    return entropy


def _compute_starter_diversity(
    sentences: list[str],
    doc: Any,
) -> float:
    """Unique first-word lemmas / total sentences.

    Uses spaCy lemmatisation when *doc* is available; falls back to
    lowercased first word otherwise.

    Returns 0.0 when there are no sentences.
    Implements AC-FR-PIPELINE-04.6.
    """
    if not sentences:
        return 0.0

    starters: list[str] = []

    if doc is not None:
        # Build a mapping from sentence text to its spaCy Span
        sent_spans = {sent.text: sent for sent in doc.sents}
        for sentence in sentences:
            span = sent_spans.get(sentence)
            if span is not None and len(span) > 0:
                starters.append(span[0].lemma_.lower())
            else:
                # Fallback for unmatched sentences
                first_word = sentence.split()[0] if sentence.split() else ""
                starters.append(first_word.lower())
    else:
        for sentence in sentences:
            words = sentence.split()
            first_word = words[0].lower() if words else ""
            starters.append(first_word)

    unique_starters = len(set(starters))
    return unique_starters / len(sentences)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_naturalness(
    sentences: list[str],
    doc: Any,
) -> NaturalnessResult:
    """Analyse naturalness of *sentences*. Implements FR-PIPELINE-04.

    Computes burstiness, length skewness, hapax legomena ratio,
    Zipf R² conformity, punctuation entropy, and sentence starter
    diversity.

    Args:
        sentences: Sentence texts produced by Stage 0.
        doc: The spaCy ``Doc`` (used for lemmatisation in starter
            diversity; may be ``None`` for Tier 0 fallback).

    Returns:
        A :class:`NaturalnessResult` with all naturalness metrics.
    """
    lengths = _sentence_lengths(sentences)

    return NaturalnessResult(
        burstiness=_compute_burstiness(lengths),
        length_skewness=_compute_length_skewness(lengths),
        hapax_ratio=_compute_hapax_ratio(sentences),
        zipf_r_squared=_compute_zipf_r_squared(sentences),
        punctuation_entropy=_compute_punctuation_entropy(sentences),
        starter_diversity=_compute_starter_diversity(sentences, doc),
    )
