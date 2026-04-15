"""Tests for the vocabulary analyzer (Stage 1).

Validates the ``analyze_vocabulary`` function against FR-PIPELINE-05
acceptance criteria.
"""

from __future__ import annotations

import dataclasses
from unittest.mock import MagicMock

from phraseturner.pipeline.vocabulary import (
    VocabularyResult,
    _compute_mtld,
    _compute_passive_voice_ratio,
    _compute_ttr,
    analyze_vocabulary,
)

# ---------------------------------------------------------------------------
# TTR tests (AC-FR-PIPELINE-05.2)
# ---------------------------------------------------------------------------


class TestComputeTTR:
    """Tests for the _compute_ttr helper."""

    def test_all_unique_words(self) -> None:
        """TTR should be 1.0 when every word is unique."""
        sentences = ["alpha beta gamma delta"]
        assert _compute_ttr(sentences) == 1.0

    def test_all_same_word(self) -> None:
        """TTR should be low when the same word is repeated."""
        sentences = ["the the the the the"]
        assert _compute_ttr(sentences) == 1.0 / 5.0

    def test_mixed_case_treated_as_same(self) -> None:
        """TTR should treat 'Hello' and 'hello' as the same word."""
        sentences = ["Hello hello HELLO"]
        assert _compute_ttr(sentences) == 1.0 / 3.0

    def test_non_alpha_tokens_excluded(self) -> None:
        """Tokens like '123' or '!!!' should be excluded."""
        sentences = ["hello 123 world !!!"]
        # Only 'hello' and 'world' are alphabetic
        assert _compute_ttr(sentences) == 1.0  # 2 unique / 2 total

    def test_empty_sentences(self) -> None:
        """TTR should be 0.0 for empty input."""
        assert _compute_ttr([]) == 0.0

    def test_no_alpha_words(self) -> None:
        """TTR should be 0.0 when no alphabetic words exist."""
        assert _compute_ttr(["123 456 789"]) == 0.0

    def test_multiple_sentences(self) -> None:
        """TTR should work across multiple sentences."""
        sentences = ["the cat sat", "the dog sat"]
        # Words: the(2), cat(1), sat(2), dog(1) -> 4 unique / 6 total
        result = _compute_ttr(sentences)
        assert abs(result - 4.0 / 6.0) < 1e-9


# ---------------------------------------------------------------------------
# MTLD tests (AC-FR-PIPELINE-05.1)
# ---------------------------------------------------------------------------


class TestComputeMTLD:
    """Tests for the _compute_mtld helper."""

    def test_empty_text(self) -> None:
        """MTLD should be 0.0 for empty input."""
        assert _compute_mtld([]) == 0.0

    def test_whitespace_only(self) -> None:
        """MTLD should be 0.0 for whitespace-only input."""
        assert _compute_mtld(["   "]) == 0.0

    def test_short_text_returns_zero(self) -> None:
        """MTLD should be 0.0 for texts with fewer than 10 words."""
        assert _compute_mtld(["one two three"]) == 0.0

    def test_sufficient_text_returns_positive(self) -> None:
        """MTLD should return a positive value for sufficiently long text."""
        sentences = [
            "The quick brown fox jumps over the lazy dog near the river.",
            "A beautiful sunset painted the sky with vibrant colours.",
            "Scientists discovered a new species in the deep ocean.",
        ]
        result = _compute_mtld(sentences)
        assert result > 0.0


# ---------------------------------------------------------------------------
# Passive voice ratio tests (AC-FR-PIPELINE-05.3)
# ---------------------------------------------------------------------------


class TestComputePassiveVoiceRatio:
    """Tests for the _compute_passive_voice_ratio helper."""

    def test_none_doc_returns_zero(self) -> None:
        """Should return 0.0 when doc is None (Tier 0 fallback)."""
        assert _compute_passive_voice_ratio(["Hello world."], None) == 0.0

    def test_empty_sentences_returns_zero(self) -> None:
        """Should return 0.0 for empty sentence list."""
        assert _compute_passive_voice_ratio([], MagicMock()) == 0.0

    def test_detects_passive_via_nsubjpass(self) -> None:
        """Should detect passive voice via nsubjpass dependency label."""
        token_passive = MagicMock()
        token_passive.dep_ = "nsubjpass"

        token_active = MagicMock()
        token_active.dep_ = "nsubj"

        sent_passive = MagicMock()
        sent_passive.__iter__ = lambda self: iter([token_passive])

        sent_active = MagicMock()
        sent_active.__iter__ = lambda self: iter([token_active])

        doc = MagicMock()
        doc.sents = [sent_passive, sent_active]

        sentences = ["The ball was kicked.", "The boy kicked the ball."]
        result = _compute_passive_voice_ratio(sentences, doc)
        assert result == 0.5  # 1 passive / 2 sentences

    def test_detects_passive_via_auxpass(self) -> None:
        """Should detect passive voice via auxpass dependency label."""
        token = MagicMock()
        token.dep_ = "auxpass"

        sent = MagicMock()
        sent.__iter__ = lambda self: iter([token])

        doc = MagicMock()
        doc.sents = [sent]

        result = _compute_passive_voice_ratio(["It was done."], doc)
        assert result == 1.0

    def test_no_passive_returns_zero(self) -> None:
        """Should return 0.0 when no passive constructions found."""
        token = MagicMock()
        token.dep_ = "nsubj"

        sent = MagicMock()
        sent.__iter__ = lambda self: iter([token])

        doc = MagicMock()
        doc.sents = [sent]

        result = _compute_passive_voice_ratio(["I ran fast."], doc)
        assert result == 0.0


# ---------------------------------------------------------------------------
# Integration: analyze_vocabulary (FR-PIPELINE-05)
# ---------------------------------------------------------------------------


class TestAnalyzeVocabulary:
    """Tests for the public analyze_vocabulary function."""

    def test_returns_vocabulary_result(self) -> None:
        """Should return a VocabularyResult dataclass."""
        sentences = [
            "The quick brown fox jumps over the lazy dog near the river.",
            "A beautiful sunset painted the sky with vibrant colours.",
            "Scientists discovered a new species in the deep ocean.",
        ]
        result = analyze_vocabulary(sentences, None)
        assert isinstance(result, VocabularyResult)

    def test_ttr_in_valid_range(self) -> None:
        """TTR should be in (0.0, 1.0] for non-empty text."""
        sentences = ["Hello world this is a test sentence with words."]
        result = analyze_vocabulary(sentences, None)
        assert 0.0 < result.ttr <= 1.0

    def test_passive_zero_without_doc(self) -> None:
        """Passive voice ratio should be 0.0 when doc is None."""
        sentences = ["The ball was kicked by the boy."]
        result = analyze_vocabulary(sentences, None)
        assert result.passive_voice_ratio == 0.0

    def test_empty_input(self) -> None:
        """Should handle empty input gracefully."""
        result = analyze_vocabulary([], None)
        assert result.ttr == 0.0
        assert result.mtld == 0.0
        assert result.passive_voice_ratio == 0.0

    def test_frozen_dataclass(self) -> None:
        """VocabularyResult should be immutable."""
        result = analyze_vocabulary(["Hello world."], None)
        try:
            result.ttr = 0.5  # type: ignore[misc]
            msg = "Should have raised FrozenInstanceError"
            raise AssertionError(msg)
        except dataclasses.FrozenInstanceError:
            pass
