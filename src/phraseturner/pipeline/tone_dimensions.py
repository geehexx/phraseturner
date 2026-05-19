"""Tone dimension scoring — F-score formality and 6-dimension composite.

Implements the Heylighen & Dewaele (1999) F-score formality metric and
composite scoring for all 6 tone dimensions used in Stage 5 alignment.

Implements C3 (formality scoring) and C8 (all 6 tone dimensions).
Requirements: FR-PIPELINE-06, FR-HEALTH-05.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from phraseturner.pipeline.additional import AdditionalSignalsResult
    from phraseturner.pipeline.naturalness import NaturalnessResult
    from phraseturner.pipeline.tone import ToneResult
    from phraseturner.pipeline.vocabulary import VocabularyResult

# ---------------------------------------------------------------------------
# POS tag sets for F-score computation
# ---------------------------------------------------------------------------

_FORMAL_POS: frozenset[str] = frozenset({"NOUN", "ADJ", "ADP", "DET"})
"""POS tags that increase formality in the F-score formula."""

_INFORMAL_POS: frozenset[str] = frozenset({"PRON", "VERB", "ADV", "INTJ"})
"""POS tags that decrease formality in the F-score formula."""

_PERSONAL_PRONOUNS: frozenset[str] = frozenset(
    {
        "i",
        "me",
        "my",
        "mine",
        "myself",
        "you",
        "your",
        "yours",
        "yourself",
        "we",
        "us",
        "our",
        "ours",
        "ourselves",
    }
)
"""First and second person pronouns for personal pronoun density."""

_EXCLAMATION_CHARS: frozenset[str] = frozenset({"!", "?"})
"""Characters used to detect exclamatory/interrogative sentences."""

_FILLER_WORDS: frozenset[str] = frozenset(
    {
        "basically",
        "literally",
        "actually",
        "honestly",
        "obviously",
        "clearly",
        "simply",
        "just",
        "really",
        "very",
        "quite",
        "pretty",
        "rather",
        "somewhat",
        "kind of",
        "sort of",
    }
)
"""Common filler words that inflate verbosity without adding information."""

_MODAL_VERBS: frozenset[str] = frozenset(
    {
        "can",
        "could",
        "may",
        "might",
        "must",
        "shall",
        "should",
        "will",
        "would",
        "ought",
    }
)
"""Modal verbs that reduce confidence when overused."""

_INCLUSIVE_PRONOUNS: frozenset[str] = frozenset(
    {
        "we",
        "us",
        "our",
        "ours",
        "ourselves",
    }
)
"""Inclusive pronouns that increase warmth."""

_IMPERATIVE_STARTERS: frozenset[str] = frozenset(
    {
        "do",
        "don't",
        "please",
        "make",
        "ensure",
        "check",
        "use",
        "add",
        "remove",
        "update",
        "create",
        "run",
        "set",
        "get",
        "note",
        "remember",
        "consider",
        "avoid",
        "keep",
    }
)
"""Common imperative sentence starters for directness scoring."""


# ---------------------------------------------------------------------------
# F-score formality (Heylighen & Dewaele 1999)
# ---------------------------------------------------------------------------


def compute_formality_score(
    doc: Any,
    contraction_density: float,
    formal_marker_count: int,
) -> float:
    """Compute composite formality score using F-score (Heylighen & Dewaele 1999).

    F = (noun_freq + adj_freq + prep_freq + article_freq
         - pronoun_freq - verb_freq - adverb_freq - interjection_freq + 100) / 2

    Normalised to [0, 1] by dividing by 100, then combined with
    contraction density and formal marker density.

    Args:
        doc: spaCy Doc object, or None for Tier 0 fallback.
        contraction_density: Contractions / total words (from ToneResult).
        formal_marker_count: Count of formal markers detected (from ToneResult).

    Returns:
        Composite formality score in [0.0, 1.0].
    """
    if doc is None:
        return max(0.0, min(1.0, 0.75 * (1.0 - contraction_density) + 0.25 * 0.5))

    formal_count = 0
    informal_count = 0
    total_tokens = 0
    personal_pronoun_count = 0

    for token in doc:
        if not token.is_alpha:
            continue
        total_tokens += 1
        if token.pos_ in _FORMAL_POS:
            formal_count += 1
        if token.pos_ in _INFORMAL_POS:
            informal_count += 1
        if token.text.lower() in _PERSONAL_PRONOUNS:
            personal_pronoun_count += 1

    if total_tokens == 0:
        return 0.5

    formal_freq = (formal_count / total_tokens) * 100.0
    informal_freq = (informal_count / total_tokens) * 100.0
    f_raw = (formal_freq - informal_freq + 100.0) / 2.0
    f_score = max(0.0, min(1.0, f_raw / 100.0))

    formal_marker_density = min(1.0, formal_marker_count / max(total_tokens / 100.0, 1.0))
    personal_pronoun_density = personal_pronoun_count / total_tokens

    n_sents_doc = sum(1 for _ in doc.sents) if doc is not None else 1
    avg_sent_len_doc = total_tokens / max(1, n_sents_doc) if doc is not None else 15.0
    f_score_adjusted = f_score * (0.8 if avg_sent_len_doc < 10.0 else 1.0)  # noqa: PLR2004

    composite = (
        0.35 * f_score_adjusted
        + 0.35 * (1.0 - contraction_density)
        + 0.15 * formal_marker_density
        + 0.15 * (1.0 - personal_pronoun_density)
    )
    return max(0.0, min(1.0, composite))


# ---------------------------------------------------------------------------
# Shared derived signals for tone dimension scoring
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _DerivedSignals:
    """Pre-computed signals shared across all 6 tone dimensions."""

    hedge_density: float
    info_density: float
    modal_density: float
    assertion_ratio: float
    passive_voice_ratio: float
    exclamation_density: float
    inclusive_pronoun_density: float
    imperative_ratio: float
    question_ratio: float
    burstiness: float
    length_variation: float
    avg_sent_len: float
    filler_density: float


def _strip_punct(word: str) -> str:
    """Strip common punctuation from a word for vocabulary matching."""
    return word.strip(".,;:!?\"'()[]")


def _compute_text_densities(
    additional: AdditionalSignalsResult | None,
    total_words: int,
    n_sentences: int,
    stripped_words: list[str],
    doc: Any,
) -> tuple[float, float, float, float, float]:
    """Compute hedge, info, modal, assertion, and passive densities.

    Returns:
        Tuple of (hedge_density, info_density, modal_density,
        assertion_ratio, passive_voice_ratio).
    """
    hedge_density = 0.0
    info_density = 0.5
    if additional is not None and additional.per_sentence:
        total_hedges = sum(s.hedge_count for s in additional.per_sentence)
        hedge_density = total_hedges / max(total_words, 1)
        densities = [s.information_density for s in additional.per_sentence]
        info_density = sum(densities) / len(densities) if densities else 0.5

    modal_count = sum(1 for w in stripped_words if w in _MODAL_VERBS)
    modal_density = modal_count / max(total_words, 1)

    if additional is not None and additional.per_sentence and n_sentences > 0:
        asserted = sum(1 for s in additional.per_sentence if s.hedge_count == 0)
        assertion_ratio = asserted / n_sentences
    else:
        assertion_ratio = 0.5

    passive_count = 0
    if doc is not None:
        for token in doc:
            if token.dep_ in {"nsubjpass", "auxpass"}:
                passive_count += 1
    passive_voice_ratio = min(1.0, passive_count / max(n_sentences, 1))

    return hedge_density, info_density, modal_density, assertion_ratio, passive_voice_ratio


def _compute_sentence_ratios(
    sentences: list[str],
    stripped_words: list[str],
    total_words: int,
    n_sentences: int,
    naturalness: NaturalnessResult | None,
) -> tuple[float, float, float, float, float, float, float]:
    """Compute sentence-level ratios for tone dimensions.

    Returns:
        Tuple of (exclamation_density, inclusive_pronoun_density,
        imperative_ratio, question_ratio, burstiness,
        length_variation, filler_density).
    """
    exclamation_count = sum(
        1 for s in sentences if s.rstrip() and s.rstrip()[-1] in _EXCLAMATION_CHARS
    )
    exclamation_density = exclamation_count / max(n_sentences, 1)

    inclusive_count = sum(1 for w in stripped_words if w in _INCLUSIVE_PRONOUNS)
    inclusive_pronoun_density = inclusive_count / max(total_words, 1)

    imperative_count = sum(
        1
        for s in sentences
        if s.split() and _strip_punct(s.split()[0].lower()) in _IMPERATIVE_STARTERS
    )
    imperative_ratio = imperative_count / max(n_sentences, 1)

    question_count = sum(1 for s in sentences if s.rstrip().endswith("?"))
    question_ratio = question_count / max(n_sentences, 1)

    burstiness = 0.5
    length_variation = 0.5
    if naturalness is not None:
        burstiness = naturalness.burstiness
        length_variation = min(1.0, naturalness.burstiness)

    filler_count = sum(1 for w in stripped_words if w in _FILLER_WORDS)
    filler_density = filler_count / max(total_words, 1)

    return (
        exclamation_density,
        inclusive_pronoun_density,
        imperative_ratio,
        question_ratio,
        burstiness,
        length_variation,
        filler_density,
    )


def _compute_derived_signals(  # noqa: PLR0913
    tone: ToneResult,
    additional: AdditionalSignalsResult | None,
    naturalness: NaturalnessResult | None,
    doc: Any,
    sentences: list[str],
    text: str,
) -> _DerivedSignals:
    """Compute all shared derived signals from pipeline stage results.

    Args:
        tone: ToneResult from Stage 1.
        additional: AdditionalSignalsResult from Stage 1 (may be None).
        naturalness: NaturalnessResult from Stage 1 (may be None).
        doc: spaCy Doc object (may be None for Tier 0).
        sentences: List of sentence strings.
        text: Full input text.

    Returns:
        Pre-computed signals for dimension scoring.
    """
    total_words = sum(len(s.split()) for s in sentences)
    n_sentences = len(sentences)
    stripped_words = [_strip_punct(w) for w in text.lower().split()]

    hedge_d, info_d, modal_d, assert_r, passive_r = _compute_text_densities(
        additional,
        total_words,
        n_sentences,
        stripped_words,
        doc,
    )
    (excl_d, incl_d, imper_r, quest_r, burst, len_var, filler_d) = _compute_sentence_ratios(
        sentences,
        stripped_words,
        total_words,
        n_sentences,
        naturalness,
    )

    return _DerivedSignals(
        hedge_density=hedge_d,
        info_density=info_d,
        modal_density=modal_d,
        assertion_ratio=assert_r,
        passive_voice_ratio=passive_r,
        exclamation_density=excl_d,
        inclusive_pronoun_density=incl_d,
        imperative_ratio=imper_r,
        question_ratio=quest_r,
        burstiness=burst,
        length_variation=len_var,
        avg_sent_len=total_words / max(n_sentences, 1),
        filler_density=filler_d,
    )


# ---------------------------------------------------------------------------
# Per-dimension score functions
# ---------------------------------------------------------------------------


def _score_confidence(sig: _DerivedSignals, compound: float) -> float:
    """Compute confidence dimension score."""
    score = (
        0.40 * (1.0 - min(sig.hedge_density * 10.0, 1.0))
        + 0.30 * (1.0 - min(sig.modal_density * 10.0, 1.0))
        + 0.20 * sig.assertion_ratio
        + 0.10 * abs(compound)
    )
    return max(0.0, min(1.0, score))


def _score_warmth(sig: _DerivedSignals, compound: float, negative: float) -> float:
    """Compute warmth dimension score."""
    score = (
        0.35 * min(sig.inclusive_pronoun_density * 20.0, 1.0)
        + 0.35 * max(0.0, compound)
        + 0.20 * (1.0 - negative)
        + 0.10 * min(sig.exclamation_density, 1.0)
    )
    return max(0.0, min(1.0, score))


def _score_directness(sig: _DerivedSignals) -> float:
    """Compute directness dimension score."""
    score = (
        0.35 * (1.0 - min(sig.hedge_density * 10.0, 1.0))
        + 0.30 * (1.0 - sig.passive_voice_ratio)
        + 0.20 * sig.imperative_ratio
        + 0.15 * (1.0 - sig.question_ratio)
    )
    return max(0.0, min(1.0, score))


def _score_energy(sig: _DerivedSignals) -> float:
    """Compute energy dimension score."""
    score = (
        0.35 * min(sig.burstiness, 1.0)
        + 0.25 * min(sig.exclamation_density, 1.0)
        + 0.25 * (1.0 - sig.passive_voice_ratio)
        + 0.15 * min(sig.length_variation, 1.0)
    )
    return max(0.0, min(1.0, score))


def _score_verbosity(sig: _DerivedSignals) -> float:
    """Compute verbosity dimension score."""
    score = (
        0.35 * min(sig.avg_sent_len / 30.0, 1.0)
        + 0.25 * min(sig.filler_density * 20.0, 1.0)
        + 0.25 * (1.0 - sig.info_density)
        + 0.15 * 0.0  # reserved for future signal
    )
    return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# 6-dimension tone scoring (orchestrator)
# ---------------------------------------------------------------------------


def compute_tone_dimensions(  # noqa: PLR0913
    tone: ToneResult,
    vocabulary: VocabularyResult | None,
    additional: AdditionalSignalsResult | None,
    naturalness: NaturalnessResult | None,
    doc: Any,
    sentences: list[str],
    text: str,
) -> dict[str, float]:
    """Compute all 6 tone dimension scores from pipeline stage results.

    Dimensions:
    - formality: F-score composite (Heylighen & Dewaele 1999)
    - confidence: hedge/modal density, assertion ratio, sentiment
    - warmth: inclusive pronouns, positive sentiment, exclamation density
    - directness: hedge density, passive voice, imperative ratio
    - energy: burstiness, exclamation density, passive voice, length variation
    - verbosity: avg sentence length, filler density, information density

    Args:
        tone: ToneResult from Stage 1 tone analyzer.
        vocabulary: VocabularyResult from Stage 1 vocabulary analyzer (may be None).
        additional: AdditionalSignalsResult from Stage 1 (may be None).
        naturalness: NaturalnessResult from Stage 1 (may be None).
        doc: spaCy Doc object (may be None for Tier 0).
        sentences: List of sentence strings from Stage 0.
        text: Full input text.

    Returns:
        Dict mapping each of the 6 dimension names to a score in [0.0, 1.0].
    """
    compound = tone.overall_sentiment.compound
    sig = _compute_derived_signals(tone, additional, naturalness, doc, sentences, text)

    return {
        "formality": compute_formality_score(
            doc,
            tone.contraction_density,
            tone.formal_marker_count,
        ),
        "confidence": _score_confidence(sig, compound),
        "warmth": _score_warmth(sig, compound, tone.overall_sentiment.negative),
        "directness": _score_directness(sig),
        "energy": _score_energy(sig),
        "verbosity": _score_verbosity(sig),
    }
