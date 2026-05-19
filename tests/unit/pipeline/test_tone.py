"""Tests for the tone analyzer (Stage 1).

Validates the ``analyze_tone`` function against FR-PIPELINE-06
acceptance criteria.
"""

from __future__ import annotations

import dataclasses
from unittest.mock import MagicMock

from phraseturner.pipeline.tone import (
    SentimentScores,
    ToneResult,
    _compute_contraction_density,
    _detect_latin_abbreviations,
    _detect_nominalizations,
    _detect_passive_constructions,
    _vader_scores,
    analyze_tone,
)

# ---------------------------------------------------------------------------
# VADER sentiment tests (FR-PIPELINE-06)
# ---------------------------------------------------------------------------


class TestVaderScores:
    """Tests for the _vader_scores helper."""

    def test_positive_text(self) -> None:
        """Positive text should have positive compound score."""
        result = _vader_scores("This is a great and wonderful day!")
        assert result.compound > 0.0
        assert result.positive > 0.0

    def test_negative_text(self) -> None:
        """Negative text should have negative compound score."""
        result = _vader_scores("This is terrible and awful.")
        assert result.compound < 0.0
        assert result.negative > 0.0

    def test_neutral_text(self) -> None:
        """Neutral text should have compound near zero."""
        result = _vader_scores("The table is in the room.")
        assert abs(result.compound) < 0.5
        assert result.neutral > 0.5

    def test_returns_sentiment_scores(self) -> None:
        """Should return a SentimentScores dataclass."""
        result = _vader_scores("Hello world.")
        assert isinstance(result, SentimentScores)

    def test_scores_sum_approximately_one(self) -> None:
        """Positive + negative + neutral should sum to ~1.0."""
        result = _vader_scores("I love this amazing product!")
        total = result.positive + result.negative + result.neutral
        assert abs(total - 1.0) < 0.01


# ---------------------------------------------------------------------------
# Contraction density tests (FR-PIPELINE-06)
# ---------------------------------------------------------------------------


class TestContractionDensity:
    """Tests for the _compute_contraction_density helper."""

    def test_no_contractions(self) -> None:
        """Should return 0.0 when no contractions present."""
        assert _compute_contraction_density(["I am going to the store."]) == 0.0

    def test_all_contractions(self) -> None:
        """Should return high density when text is mostly contractions."""
        result = _compute_contraction_density(["don't can't won't"])
        assert result == 1.0

    def test_mixed_text(self) -> None:
        """Should compute correct ratio for mixed text."""
        # "I don't think it's right" -> 5 words, 2 contractions
        result = _compute_contraction_density(["I don't think it's right"])
        assert abs(result - 2.0 / 5.0) < 1e-9

    def test_empty_input(self) -> None:
        """Should return 0.0 for empty input."""
        assert _compute_contraction_density([]) == 0.0

    def test_case_insensitive(self) -> None:
        """Should match contractions regardless of case."""
        result = _compute_contraction_density(["DON'T WORRY"])
        assert result > 0.0

    def test_multiple_sentences(self) -> None:
        """Should work across multiple sentences."""
        sentences = ["I can't go.", "She won't stay."]
        # 6 words total, 2 contractions
        result = _compute_contraction_density(sentences)
        assert abs(result - 2.0 / 6.0) < 1e-9


# ---------------------------------------------------------------------------
# Latin abbreviation detection tests (FR-PIPELINE-06)
# ---------------------------------------------------------------------------


class TestLatinAbbreviations:
    """Tests for the _detect_latin_abbreviations helper."""

    def test_detects_eg(self) -> None:
        """Should detect 'e.g.' abbreviation."""
        markers = _detect_latin_abbreviations("Use a tool, e.g. a hammer.")
        assert any("e.g." in m.lower() for m in markers)

    def test_detects_ie(self) -> None:
        """Should detect 'i.e.' abbreviation."""
        markers = _detect_latin_abbreviations("The result, i.e. the answer.")
        assert any("i.e." in m.lower() for m in markers)

    def test_detects_etc(self) -> None:
        """Should detect 'etc.' abbreviation."""
        markers = _detect_latin_abbreviations("Apples, oranges, etc.")
        assert any("etc." in m.lower() for m in markers)

    def test_detects_per_se(self) -> None:
        """Should detect 'per se' phrase."""
        markers = _detect_latin_abbreviations("It is not wrong per se.")
        assert any("per se" in m.lower() for m in markers)

    def test_detects_ad_hoc(self) -> None:
        """Should detect 'ad hoc' phrase."""
        markers = _detect_latin_abbreviations("An ad hoc committee was formed.")
        assert any("ad hoc" in m.lower() for m in markers)

    def test_no_latin_returns_empty(self) -> None:
        """Should return empty list when no Latin abbreviations found."""
        markers = _detect_latin_abbreviations("The cat sat on the mat.")
        assert markers == []

    def test_case_insensitive(self) -> None:
        """Should detect abbreviations regardless of case."""
        markers = _detect_latin_abbreviations("E.G. this example.")
        assert len(markers) > 0


# ---------------------------------------------------------------------------
# Passive construction detection tests (FR-PIPELINE-06)
# ---------------------------------------------------------------------------


class TestPassiveConstructions:
    """Tests for the _detect_passive_constructions helper."""

    def test_none_doc_returns_empty(self) -> None:
        """Should return empty list when doc is None."""
        assert _detect_passive_constructions(None) == []

    def test_detects_nsubjpass(self) -> None:
        """Should detect nsubjpass dependency label."""
        token = MagicMock()
        token.dep_ = "nsubjpass"
        token.text = "ball"

        doc = MagicMock()
        doc.__iter__ = lambda self: iter([token])

        markers = _detect_passive_constructions(doc)
        assert len(markers) == 1
        assert "nsubjpass:ball" in markers[0]

    def test_detects_auxpass(self) -> None:
        """Should detect auxpass dependency label."""
        token = MagicMock()
        token.dep_ = "auxpass"
        token.text = "was"

        doc = MagicMock()
        doc.__iter__ = lambda self: iter([token])

        markers = _detect_passive_constructions(doc)
        assert len(markers) == 1
        assert "auxpass:was" in markers[0]

    def test_ignores_active_voice(self) -> None:
        """Should not flag active voice tokens."""
        token = MagicMock()
        token.dep_ = "nsubj"
        token.text = "cat"

        doc = MagicMock()
        doc.__iter__ = lambda self: iter([token])

        markers = _detect_passive_constructions(doc)
        assert markers == []


# ---------------------------------------------------------------------------
# Nominalization detection tests (FR-PIPELINE-06)
# ---------------------------------------------------------------------------


class TestNominalizations:
    """Tests for the _detect_nominalizations helper."""

    def test_detects_tion_suffix(self) -> None:
        """Should detect words ending in -tion."""
        markers = _detect_nominalizations(["The implementation was complete."])
        assert "implementation" in markers

    def test_detects_ment_suffix(self) -> None:
        """Should detect words ending in -ment."""
        markers = _detect_nominalizations(["The development of the project."])
        assert "development" in markers

    def test_detects_ness_suffix(self) -> None:
        """Should detect words ending in -ness."""
        markers = _detect_nominalizations(["The effectiveness was measured."])
        assert "effectiveness" in markers

    def test_ignores_short_words(self) -> None:
        """Should ignore words shorter than 6 characters."""
        markers = _detect_nominalizations(["The dance was nice."])
        assert "dance" not in markers

    def test_deduplicates(self) -> None:
        """Should not report the same word twice."""
        markers = _detect_nominalizations(["The implementation and implementation were good."])
        assert markers.count("implementation") == 1

    def test_empty_input(self) -> None:
        """Should return empty list for empty input."""
        assert _detect_nominalizations([]) == []

    def test_strips_punctuation(self) -> None:
        """Should strip trailing punctuation before checking suffix."""
        markers = _detect_nominalizations(["The implementation."])
        assert "implementation" in markers


# ---------------------------------------------------------------------------
# Integration: analyze_tone (FR-PIPELINE-06)
# ---------------------------------------------------------------------------


class TestAnalyzeTone:
    """Tests for the public analyze_tone function."""

    def test_returns_tone_result(self) -> None:
        """Should return a ToneResult dataclass."""
        sentences = ["I love this.", "It is terrible."]
        result = analyze_tone(sentences, None)
        assert isinstance(result, ToneResult)

    def test_per_sentence_count_matches(self) -> None:
        """Per-sentence sentiment list should match sentence count."""
        sentences = ["Hello.", "World.", "Test."]
        result = analyze_tone(sentences, None)
        assert len(result.per_sentence_sentiment) == 3

    def test_overall_sentiment_present(self) -> None:
        """Overall sentiment should be computed."""
        result = analyze_tone(["Great day!"], None)
        assert isinstance(result.overall_sentiment, SentimentScores)

    def test_contraction_density_computed(self) -> None:
        """Contraction density should be computed."""
        result = analyze_tone(["I don't think so."], None)
        assert result.contraction_density > 0.0

    def test_formal_markers_with_latin(self) -> None:
        """Should detect Latin abbreviations as formal markers."""
        result = analyze_tone(["Use e.g. a hammer."], None)
        assert result.formal_marker_count > 0
        assert len(result.formal_markers) > 0

    def test_formal_markers_with_nominalizations(self) -> None:
        """Should detect nominalizations as formal markers."""
        result = analyze_tone(["The implementation was complete."], None)
        assert any("implementation" in m for m in result.formal_markers)

    def test_empty_input(self) -> None:
        """Should handle empty input gracefully."""
        result = analyze_tone([], None)
        assert result.per_sentence_sentiment == []
        assert result.contraction_density == 0.0
        assert result.formal_marker_count == 0

    def test_frozen_dataclass(self) -> None:
        """ToneResult should be immutable."""
        result = analyze_tone(["Hello."], None)
        try:
            result.contraction_density = 0.5  # type: ignore[misc]
            msg = "Should have raised FrozenInstanceError"
            raise AssertionError(msg)
        except dataclasses.FrozenInstanceError:
            pass

    def test_no_doc_passive_markers_empty(self) -> None:
        """Passive markers should be empty when doc is None."""
        result = analyze_tone(
            ["The ball was kicked by the boy."],
            None,
        )
        # No passive markers without spaCy doc
        passive_markers = [m for m in result.formal_markers if ":" in m]
        assert passive_markers == []
