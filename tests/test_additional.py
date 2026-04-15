"""Tests for the additional signals analyzer (Stage 1).

Validates hedging detection, information density, specificity scoring,
and discourse coherence.

Requirements: FR-PIPELINE-08.
"""

from __future__ import annotations

from typing import Any

import pytest
import spacy

from phraseturner.pipeline.additional import (
    AdditionalSignalsResult,
    SentenceSignals,
    _compute_coherence_pair,
    _compute_sentence_density_heuristic,
    _compute_sentence_density_spacy,
    _compute_specificity,
    _detect_hedges,
    _extract_content_lemmas_spacy,
    _extract_content_words_plain,
    _extract_entity_texts,
    _jaccard,
    _specificity_from_spacy,
    _specificity_heuristic,
    analyze_additional,
)


@pytest.fixture(scope="module")
def nlp() -> Any:
    """Load spaCy model once for the test module."""
    return spacy.load("en_core_web_sm")


# =========================================================================
# Hedging detection
# =========================================================================


class TestDetectHedges:
    """Tests for _detect_hedges."""

    def test_single_hedge_word(self) -> None:
        result = _detect_hedges("This is perhaps the best option.")
        assert "perhaps" in result

    def test_multiple_hedge_words(self) -> None:
        result = _detect_hedges("Maybe we could possibly try this.")
        assert "maybe" in result
        assert "could" in result
        assert "possibly" in result

    def test_multi_word_phrase(self) -> None:
        result = _detect_hedges("It is sort of working now.")
        assert "sort of" in result

    def test_case_insensitive(self) -> None:
        result = _detect_hedges("PERHAPS this MIGHT work.")
        assert "perhaps" in result
        assert "might" in result

    def test_no_hedges(self) -> None:
        result = _detect_hedges("The cat sat on the mat.")
        assert result == []

    def test_empty_sentence(self) -> None:
        result = _detect_hedges("")
        assert result == []

    def test_hedge_with_punctuation(self) -> None:
        result = _detect_hedges("Apparently, this is true.")
        assert "apparently" in result


# =========================================================================
# Information density
# =========================================================================


class TestInformationDensity:
    """Tests for information density computation."""

    def test_spacy_density_range(self, nlp: Any) -> None:
        doc = nlp("The quick brown fox jumps over the lazy dog.")
        spans = list(doc.sents)
        density = _compute_sentence_density_spacy(spans[0])
        assert 0.0 <= density <= 1.0

    def test_spacy_density_content_heavy(self, nlp: Any) -> None:
        """Sentence with many content words should have high density."""
        doc = nlp("Beautiful large red expensive cars drive quickly.")
        spans = list(doc.sents)
        density = _compute_sentence_density_spacy(spans[0])
        assert density > 0.5

    def test_heuristic_returns_default(self) -> None:
        density = _compute_sentence_density_heuristic("Hello world.")
        assert density == pytest.approx(0.6)

    def test_heuristic_empty_returns_zero(self) -> None:
        density = _compute_sentence_density_heuristic("")
        assert density == 0.0

    def test_heuristic_no_alpha_returns_zero(self) -> None:
        density = _compute_sentence_density_heuristic("123 456 789")
        assert density == 0.0


# =========================================================================
# Specificity scoring
# =========================================================================


class TestSpecificity:
    """Tests for specificity scoring."""

    def test_spacy_specificity_range(self, nlp: Any) -> None:
        doc = nlp("Apple released 3 new products in California.")
        spans = list(doc.sents)
        score = _specificity_from_spacy(spans[0])
        assert 0.0 <= score <= 1.0

    def test_spacy_specificity_with_entities(self, nlp: Any) -> None:
        """Sentences with named entities should score higher."""
        doc_specific = nlp("Google announced 5 new features in New York.")
        doc_vague = nlp("The situation involves various considerations.")
        spans_specific = list(doc_specific.sents)
        spans_vague = list(doc_vague.sents)
        score_specific = _specificity_from_spacy(spans_specific[0])
        score_vague = _specificity_from_spacy(spans_vague[0])
        assert score_specific > score_vague

    def test_heuristic_specificity_range(self) -> None:
        score = _specificity_heuristic("There are 5 items on the table.")
        assert 0.0 <= score <= 1.0

    def test_heuristic_empty_returns_zero(self) -> None:
        score = _specificity_heuristic("")
        assert score == 0.0

    def test_compute_specificity_with_doc(self, nlp: Any) -> None:
        doc = nlp("The cat sat on the mat.")
        spans = list(doc.sents)
        score = _compute_specificity(spans[0], "The cat sat on the mat.")
        assert 0.0 <= score <= 1.0

    def test_compute_specificity_without_doc(self) -> None:
        score = _compute_specificity(None, "The cat sat on the mat.")
        assert 0.0 <= score <= 1.0


# =========================================================================
# Discourse coherence
# =========================================================================


class TestCoherence:
    """Tests for discourse coherence computation."""

    def test_jaccard_identical_sets(self) -> None:
        assert _jaccard({"a", "b", "c"}, {"a", "b", "c"}) == pytest.approx(1.0)

    def test_jaccard_disjoint_sets(self) -> None:
        assert _jaccard({"a", "b"}, {"c", "d"}) == pytest.approx(0.0)

    def test_jaccard_empty_sets(self) -> None:
        assert _jaccard(set(), set()) == pytest.approx(0.0)

    def test_jaccard_partial_overlap(self) -> None:
        result = _jaccard({"a", "b", "c"}, {"b", "c", "d"})
        # intersection = {b, c} = 2, union = {a, b, c, d} = 4
        assert result == pytest.approx(0.5)

    def test_content_lemmas_spacy(self, nlp: Any) -> None:
        doc = nlp("The quick brown fox jumps.")
        spans = list(doc.sents)
        lemmas = _extract_content_lemmas_spacy(spans[0])
        assert isinstance(lemmas, set)
        assert len(lemmas) > 0

    def test_content_words_plain(self) -> None:
        words = _extract_content_words_plain("The quick brown fox jumps.")
        assert "quick" in words
        assert "brown" in words
        # Short words (< 3 chars) excluded
        assert "a" not in words

    def test_entity_texts_spacy(self, nlp: Any) -> None:
        doc = nlp("Apple is based in California.")
        spans = list(doc.sents)
        entities = _extract_entity_texts(spans[0])
        assert isinstance(entities, set)

    def test_coherence_pair_with_spacy(self, nlp: Any) -> None:
        doc = nlp("The cat sat on the mat. The cat then jumped off the mat.")
        spans = list(doc.sents)
        coherence = _compute_coherence_pair(
            spans[0], spans[1],
            "The cat sat on the mat.",
            "The cat then jumped off the mat.",
        )
        assert 0.0 <= coherence <= 1.0
        # Sentences share "cat" and "mat" — should have some overlap
        assert coherence > 0.0

    def test_coherence_pair_without_spacy(self) -> None:
        coherence = _compute_coherence_pair(
            None, None,
            "The cat sat on the mat.",
            "The dog ran in the park.",
        )
        assert 0.0 <= coherence <= 1.0


# =========================================================================
# Full analyzer integration
# =========================================================================


class TestAnalyzeAdditional:
    """Tests for the analyze_additional public API."""

    def test_basic_with_spacy(self, nlp: Any) -> None:
        text = "Perhaps the situation is somewhat unclear. The data shows 5 key trends."
        doc = nlp(text)
        sentences = [s.text for s in doc.sents]
        result = analyze_additional(sentences, doc)

        assert isinstance(result, AdditionalSignalsResult)
        assert len(result.per_sentence) == len(sentences)

        # First sentence has hedges
        assert result.per_sentence[0].hedge_count > 0
        assert "perhaps" in result.per_sentence[0].hedge_words

    def test_basic_without_spacy(self) -> None:
        sentences = ["Hello world.", "Goodbye world."]
        result = analyze_additional(sentences, None)

        assert isinstance(result, AdditionalSignalsResult)
        assert len(result.per_sentence) == 2

    def test_single_sentence(self, nlp: Any) -> None:
        doc = nlp("The cat sat on the mat.")
        sentences = [s.text for s in doc.sents]
        result = analyze_additional(sentences, doc)

        assert len(result.per_sentence) == 1
        # Last (only) sentence has no coherence_to_next
        assert result.per_sentence[0].coherence_to_next is None
        assert result.mean_coherence == 0.0

    def test_empty_sentences(self) -> None:
        result = analyze_additional([], None)

        assert result.per_sentence == []
        assert result.overall_information_density == 0.0
        assert result.overall_specificity == 0.0
        assert result.mean_coherence == 0.0

    def test_density_in_range(self, nlp: Any) -> None:
        """P-inv-11: information density in [0.0, 1.0]."""
        doc = nlp("The quick brown fox jumps over the lazy dog. Another sentence here.")
        sentences = [s.text for s in doc.sents]
        result = analyze_additional(sentences, doc)

        for sig in result.per_sentence:
            assert 0.0 <= sig.information_density <= 1.0

    def test_specificity_in_range(self, nlp: Any) -> None:
        doc = nlp("Apple released 3 products. The situation is unclear.")
        sentences = [s.text for s in doc.sents]
        result = analyze_additional(sentences, doc)

        for sig in result.per_sentence:
            assert 0.0 <= sig.specificity <= 1.0

    def test_coherence_last_sentence_none(self, nlp: Any) -> None:
        doc = nlp("First sentence. Second sentence. Third sentence.")
        sentences = [s.text for s in doc.sents]
        result = analyze_additional(sentences, doc)

        # Last sentence should have None coherence
        assert result.per_sentence[-1].coherence_to_next is None
        # Others should have float values
        for sig in result.per_sentence[:-1]:
            assert sig.coherence_to_next is not None
            assert 0.0 <= sig.coherence_to_next <= 1.0

    def test_overall_density_is_mean(self, nlp: Any) -> None:
        doc = nlp("The cat sat. The dog ran.")
        sentences = [s.text for s in doc.sents]
        result = analyze_additional(sentences, doc)

        densities = [s.information_density for s in result.per_sentence]
        expected = sum(densities) / len(densities)
        assert result.overall_information_density == pytest.approx(expected)

    def test_sentence_signals_dataclass(self) -> None:
        sig = SentenceSignals(
            hedge_words=["perhaps"],
            hedge_count=1,
            information_density=0.5,
            specificity=0.3,
            coherence_to_next=0.7,
        )
        assert sig.hedge_count == 1
        assert sig.information_density == 0.5
