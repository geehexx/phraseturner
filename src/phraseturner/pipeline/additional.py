"""Stage 1 analyzer: Additional analysis signals.

Compute hedging detection, information density, specificity scoring,
and discourse coherence metrics for text analysis.

This module is CPU-bound and is called via ``asyncio.to_thread()``
by the pipeline orchestrator (Task 3.10).

Implements §4.3.
Requirements: FR-PIPELINE-08.
"""

from __future__ import annotations

import dataclasses
import re
from typing import Any

# ---------------------------------------------------------------------------
# Hedge lexicon (~30 entries)
# ---------------------------------------------------------------------------

_HEDGE_PHRASES: tuple[str, ...] = (
    "sort of",
    "kind of",
    "a bit",
    "tend to",
    "in some cases",
    "to some extent",
    "more or less",
)
"""Multi-word hedge phrases matched before single-word hedges."""

_HEDGE_WORDS: frozenset[str] = frozenset({
    "perhaps",
    "maybe",
    "possibly",
    "somewhat",
    "rather",
    "quite",
    "fairly",
    "slightly",
    "apparently",
    "seemingly",
    "arguably",
    "presumably",
    "supposedly",
    "generally",
    "typically",
    "usually",
    "often",
    "sometimes",
    "might",
    "could",
    "may",
    "seem",
    "appear",
})
"""Single-word hedges matched case-insensitively. FR-PIPELINE-08."""

# Pre-compiled patterns for multi-word hedge phrases (case-insensitive).
_HEDGE_PHRASE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE)
    for phrase in _HEDGE_PHRASES
)

# ---------------------------------------------------------------------------
# Content POS tags for information density
# ---------------------------------------------------------------------------

_CONTENT_POS_TAGS: frozenset[str] = frozenset({
    "NOUN", "VERB", "ADJ", "ADV", "PROPN",
})
"""spaCy POS tags considered content words. AC-FR-PIPELINE-08.2."""

# ---------------------------------------------------------------------------
# Abstract noun suffixes for specificity scoring
# ---------------------------------------------------------------------------

_ABSTRACT_SUFFIXES: tuple[str, ...] = (
    "ness", "ity", "ment", "tion", "sion", "ance", "ence",
)
"""Suffixes indicating abstract nouns. AC-FR-PIPELINE-08.3."""

_DEFAULT_DENSITY: float = 0.6
"""Heuristic content-word ratio when spaCy is unavailable."""

_QUESTION_SPECIFICITY_FLOOR: float = 0.15
"""Minimum specificity for question sentences (end with '?').

Questions inherently have fewer named entities and numbers but should
not be penalised as heavily as vague statements. AC-FR-PIPELINE-08.3.
"""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class SentenceSignals:
    """Additional signals for a single sentence.

    Attributes:
        hedge_words: Hedge words/phrases found in this sentence.
            Implements AC-FR-PIPELINE-08.1.
        hedge_count: Count of hedge words/phrases.
            Implements AC-FR-PIPELINE-08.1.
        information_density: Content words / total alphabetic tokens
            (0.0-1.0).  Implements AC-FR-PIPELINE-08.2, P-inv-11.
        specificity: Combined specificity score (0.0-1.0).
            Implements AC-FR-PIPELINE-08.3.
        coherence_to_next: Jaccard overlap with next sentence
            (``None`` for the last sentence).
            Implements AC-FR-PIPELINE-08.4.
    """

    hedge_words: list[str]
    hedge_count: int
    information_density: float
    specificity: float
    coherence_to_next: float | None


@dataclasses.dataclass(frozen=True)
class AdditionalSignalsResult:
    """Result of the additional signals analyzer.

    Attributes:
        per_sentence: Per-sentence signal breakdowns.
        overall_information_density: Mean of per-sentence densities.
        overall_specificity: Mean of per-sentence specificities.
        mean_coherence: Mean of all non-None coherence values.
    """

    per_sentence: list[SentenceSignals]
    overall_information_density: float
    overall_specificity: float
    mean_coherence: float


# ---------------------------------------------------------------------------
# Hedging detection
# ---------------------------------------------------------------------------


def _detect_hedges(sentence: str) -> list[str]:
    """Detect hedge words and phrases in *sentence*.

    Multi-word phrases are matched first, then single words.
    All matching is case-insensitive.

    Args:
        sentence: A single sentence text.

    Returns:
        List of matched hedge words/phrases (lowercased).
    """
    found: list[str] = []

    # Multi-word phrases first
    for pattern in _HEDGE_PHRASE_PATTERNS:
        for match in pattern.finditer(sentence):
            found.append(match.group().lower())

    # Single words
    for word in sentence.split():
        cleaned = word.lower().strip(".,;:!?\"'()[]")
        if cleaned in _HEDGE_WORDS:
            found.append(cleaned)

    return found


# ---------------------------------------------------------------------------
# Information density
# ---------------------------------------------------------------------------


def _compute_sentence_density_spacy(
    sent_span: Any,
) -> float:
    """Compute information density for a spaCy sentence span.

    Args:
        sent_span: A spaCy ``Span`` for one sentence.

    Returns:
        Ratio of content-word tokens to total alphabetic tokens,
        clamped to [0.0, 1.0].
    """
    content_count = 0
    alpha_count = 0

    for token in sent_span:
        if token.is_alpha:
            alpha_count += 1
            if token.pos_ in _CONTENT_POS_TAGS:
                content_count += 1

    if alpha_count == 0:
        return 0.0

    return content_count / alpha_count


def _compute_sentence_density_heuristic(sentence: str) -> float:
    """Heuristic information density when spaCy is unavailable.

    Assumes ~60% of alphabetic tokens are content words.

    Args:
        sentence: A single sentence text.

    Returns:
        ``_DEFAULT_DENSITY`` if the sentence has alphabetic words,
        otherwise 0.0.
    """
    has_alpha = any(w.isalpha() for w in sentence.split())
    return _DEFAULT_DENSITY if has_alpha else 0.0


# ---------------------------------------------------------------------------
# Specificity scoring
# ---------------------------------------------------------------------------


def _compute_specificity(
    sent_span: Any | None,
    sentence: str,
) -> float:
    """Compute specificity score for a sentence.

    Combines three signals:
    - Named entity density (NER count / total tokens)
    - Number presence (numeric tokens / total tokens)
    - Abstract noun ratio (1.0 - abstract nouns / total nouns)

    Overall = entity_density * 0.4 + number_presence * 0.3
              + (1 - abstract_ratio) * 0.3, clamped to [0.0, 1.0].

    Args:
        sent_span: A spaCy ``Span`` for one sentence, or ``None``.
        sentence: The raw sentence text (fallback).

    Returns:
        Specificity score in [0.0, 1.0].
        Implements AC-FR-PIPELINE-08.3.
    """
    if sent_span is not None:
        raw = _specificity_from_spacy(sent_span)
    else:
        raw = _specificity_heuristic(sentence)

    # Question heuristic: sentences ending with '?' have fewer named
    # entities/numbers by nature — apply a floor to avoid over-penalising.
    # AC-FR-PIPELINE-08.3.
    if sentence.rstrip().endswith('?'):
        return max(raw, _QUESTION_SPECIFICITY_FLOOR)
    return raw


def _specificity_from_spacy(sent_span: Any) -> float:
    """Compute specificity using spaCy NER and POS tags.

    Args:
        sent_span: A spaCy ``Span`` for one sentence.

    Returns:
        Specificity score in [0.0, 1.0].
    """
    total_tokens = len(sent_span)
    if total_tokens == 0:
        return 0.0

    # Named entity density
    entity_count = len(sent_span.ents)
    entity_density = entity_count / total_tokens

    # Number presence
    numeric_count = sum(1 for t in sent_span if t.like_num)
    number_presence = numeric_count / total_tokens

    # Abstract noun ratio
    noun_count = 0
    abstract_count = 0
    for token in sent_span:
        if token.pos_ == "NOUN":
            noun_count += 1
            lower = token.text.lower()
            if any(lower.endswith(s) for s in _ABSTRACT_SUFFIXES):
                abstract_count += 1

    abstract_ratio = abstract_count / noun_count if noun_count > 0 else 0.0

    # Weighted combination: higher entity/number = more specific,
    # lower abstract ratio = more specific
    raw = (
        entity_density * 0.4
        + number_presence * 0.3
        + (1.0 - abstract_ratio) * 0.3
    )
    return max(0.0, min(1.0, raw))


def _specificity_heuristic(sentence: str) -> float:
    """Heuristic specificity when spaCy is unavailable.

    Uses simple regex for numbers and suffix matching for abstract
    nouns.

    Args:
        sentence: A single sentence text.

    Returns:
        Specificity score in [0.0, 1.0].
    """
    words = sentence.split()
    total = len(words)
    if total == 0:
        return 0.0

    # Number presence (simple digit check)
    numeric_count = sum(1 for w in words if any(c.isdigit() for c in w))
    number_presence = numeric_count / total

    # Abstract noun ratio (suffix-based)
    alpha_words = [w.lower().strip(".,;:!?\"'()[]") for w in words if w.isalpha()]
    noun_like = [w for w in alpha_words if len(w) >= 4]  # noqa: PLR2004
    abstract_count = sum(
        1 for w in noun_like
        if any(w.endswith(s) for s in _ABSTRACT_SUFFIXES)
    )
    abstract_ratio = abstract_count / len(noun_like) if noun_like else 0.0

    # No entity detection without spaCy — entity_density = 0
    raw = number_presence * 0.3 + (1.0 - abstract_ratio) * 0.3
    return max(0.0, min(1.0, raw))


# ---------------------------------------------------------------------------
# Discourse coherence
# ---------------------------------------------------------------------------


def _extract_content_lemmas_spacy(sent_span: Any) -> set[str]:
    """Extract content word lemmas from a spaCy sentence span.

    Args:
        sent_span: A spaCy ``Span`` for one sentence.

    Returns:
        Set of lowercased lemmas for content words.
    """
    return {
        token.lemma_.lower()
        for token in sent_span
        if token.pos_ in _CONTENT_POS_TAGS and token.is_alpha
    }


def _extract_content_words_plain(sentence: str) -> set[str]:
    """Extract lowercased alphabetic words as a fallback.

    Args:
        sentence: A single sentence text.

    Returns:
        Set of lowercased alphabetic words (≥3 chars to skip
        function words).
    """
    return {
        w.lower().strip(".,;:!?\"'()[]")
        for w in sentence.split()
        if w.isalpha() and len(w) >= 3  # noqa: PLR2004
    }


def _extract_entity_texts(sent_span: Any) -> set[str]:
    """Extract named entity texts from a spaCy sentence span.

    Args:
        sent_span: A spaCy ``Span`` for one sentence.

    Returns:
        Set of lowercased entity texts.
    """
    return {ent.text.lower() for ent in sent_span.ents}


def _jaccard(set_a: set[str], set_b: set[str]) -> float:
    """Compute Jaccard similarity between two sets.

    Args:
        set_a: First set.
        set_b: Second set.

    Returns:
        |intersection| / |union|, or 0.0 when both sets are empty.
    """
    if not set_a and not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


# Punctuation characters to strip from word boundaries.
_STRIP_PUNCT = ".,;:!?()[]"

# Pronouns that can bridge references between sentences.
_BRIDGING_PRONOUNS: frozenset[str] = frozenset({
    "he", "she", "it", "they", "his", "her", "its", "their",
    "him", "them", "this", "that", "these", "those",
})

# Discourse markers indicating logical transitions.
_DISCOURSE_MARKERS: frozenset[str] = frozenset({
    "however", "therefore", "furthermore", "moreover", "additionally",
    "consequently", "nevertheless", "nonetheless", "meanwhile",
    "subsequently", "accordingly", "thus", "hence", "also",
    "besides", "instead", "otherwise", "similarly", "likewise",
    "although", "whereas", "while", "because", "since",
})


def _has_pronoun_bridge(sent_b: str) -> bool:
    """Check if sentence B opens with a bridging pronoun.

    Args:
        sent_b: Raw text of sentence B.

    Returns:
        True if the sentence starts with a pronoun that could refer
        to entities in the preceding sentence.
    """
    first_word = sent_b.split(maxsplit=1)[0].lower().strip(_STRIP_PUNCT) if sent_b.split() else ""
    return first_word in _BRIDGING_PRONOUNS


def _has_discourse_marker(sent_b: str) -> bool:
    """Check if sentence B opens with a transitional discourse marker.

    Args:
        sent_b: Raw text of sentence B.

    Returns:
        True if the sentence starts with a recognised discourse marker.
    """
    first_word = sent_b.split(maxsplit=1)[0].lower().strip(_STRIP_PUNCT) if sent_b.split() else ""
    return first_word in _DISCOURSE_MARKERS


def _compute_coherence_pair(
    span_a: Any | None,
    span_b: Any | None,
    sent_a: str,
    sent_b: str,
) -> float:
    """Compute coherence between two adjacent sentences.

    Combined coherence = 0.35 * vec_sim + 0.25 * jaccard
                       + 0.20 * entity_continuity
                       + 0.10 * pronoun_bridge
                       + 0.10 * discourse_marker.

    Args:
        span_a: spaCy ``Span`` for sentence A (or ``None``).
        span_b: spaCy ``Span`` for sentence B (or ``None``).
        sent_a: Raw text of sentence A.
        sent_b: Raw text of sentence B.

    Returns:
        Coherence score in [0.0, 1.0].
        Implements AC-FR-PIPELINE-08.4.
    """
    # Vector similarity via spaCy built-in word vectors
    vec_sim = 0.0
    if span_a is not None and span_b is not None:
        try:
            sim = span_a.similarity(span_b)
            vec_sim = max(0.0, min(1.0, float(sim)))
        except Exception:
            vec_sim = 0.0

    # Lexical overlap (Jaccard on content word lemmas)
    if span_a is not None and span_b is not None:
        lemmas_a = _extract_content_lemmas_spacy(span_a)
        lemmas_b = _extract_content_lemmas_spacy(span_b)
    else:
        lemmas_a = _extract_content_words_plain(sent_a)
        lemmas_b = _extract_content_words_plain(sent_b)

    jaccard_sim = _jaccard(lemmas_a, lemmas_b)

    # Entity continuity
    entity_continuity = 0.0
    if span_a is not None and span_b is not None:
        ents_a = _extract_entity_texts(span_a)
        ents_b = _extract_entity_texts(span_b)
        if ents_a:
            shared = ents_a & ents_b
            entity_continuity = len(shared) / len(ents_a)

    # Pronoun bridging: 1.0 if sentence B opens with a bridging pronoun
    pronoun_bridge = 1.0 if _has_pronoun_bridge(sent_b) else 0.0

    # Discourse marker: 1.0 if sentence B opens with a transitional word
    discourse_marker = 1.0 if _has_discourse_marker(sent_b) else 0.0

    return (
        0.35 * vec_sim
        + 0.25 * jaccard_sim
        + 0.20 * entity_continuity
        + 0.10 * pronoun_bridge
        + 0.10 * discourse_marker
    )


# ---------------------------------------------------------------------------
# Sentence span mapping
# ---------------------------------------------------------------------------


def _get_sentence_spans(doc: Any) -> list[Any]:
    """Extract sentence spans from a spaCy Doc.

    Args:
        doc: The spaCy ``Doc``, or ``None``.

    Returns:
        List of spaCy ``Span`` objects, one per sentence.
        Empty list when *doc* is ``None``.
    """
    if doc is None:
        return []
    return list(doc.sents)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_additional(
    sentences: list[str],
    doc: Any,
) -> AdditionalSignalsResult:
    """Analyse additional signals for *sentences*. Implements FR-PIPELINE-08.

    Computes hedging detection, information density, specificity
    scoring, and discourse coherence for each sentence.

    This function is CPU-bound and will be called via
    ``asyncio.to_thread()`` by the pipeline orchestrator.

    Args:
        sentences: Sentence texts produced by Stage 0.
        doc: The spaCy ``Doc`` (used for POS, NER, and lemma
            extraction; may be ``None`` for Tier 0 fallback).

    Returns:
        An :class:`AdditionalSignalsResult` with per-sentence and
        overall metrics.
    """
    spans = _get_sentence_spans(doc)
    n_sentences = len(sentences)

    per_sentence: list[SentenceSignals] = []
    densities: list[float] = []
    specificities: list[float] = []
    coherences: list[float] = []

    for i, sentence in enumerate(sentences):
        # Hedging -- AC-FR-PIPELINE-08.1
        hedges = _detect_hedges(sentence)

        # Information density -- AC-FR-PIPELINE-08.2
        if i < len(spans):
            density = _compute_sentence_density_spacy(spans[i])
        else:
            density = _compute_sentence_density_heuristic(sentence)
        densities.append(density)

        # Specificity -- AC-FR-PIPELINE-08.3
        span = spans[i] if i < len(spans) else None
        specificity = _compute_specificity(span, sentence)
        specificities.append(specificity)

        # Coherence -- AC-FR-PIPELINE-08.4
        coherence: float | None = None
        if i < n_sentences - 1:
            span_next = spans[i + 1] if (i + 1) < len(spans) else None
            coherence = _compute_coherence_pair(
                span, span_next, sentence, sentences[i + 1],
            )
            coherences.append(coherence)

        per_sentence.append(
            SentenceSignals(
                hedge_words=hedges,
                hedge_count=len(hedges),
                information_density=density,
                specificity=specificity,
                coherence_to_next=coherence,
            ),
        )

    # Overall aggregates
    overall_density = (
        sum(densities) / len(densities) if densities else 0.0
    )
    overall_specificity = (
        sum(specificities) / len(specificities) if specificities else 0.0
    )
    mean_coherence = (
        sum(coherences) / len(coherences) if coherences else 0.0
    )

    return AdditionalSignalsResult(
        per_sentence=per_sentence,
        overall_information_density=overall_density,
        overall_specificity=overall_specificity,
        mean_coherence=mean_coherence,
    )
