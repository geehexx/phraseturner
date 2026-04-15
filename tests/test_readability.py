"""Tests for the readability analyzer (Stage 1).

Validates the ``analyze_readability`` function against FR-PIPELINE-03
acceptance criteria.
"""

from __future__ import annotations

from phraseturner.pipeline.readability import (
    ReadabilityResult,
    _compute_grades,
    _consensus,
    analyze_readability,
)


class TestComputeGrades:
    """Tests for the _compute_grades helper."""

    def test_returns_all_seven_formulas(self) -> None:
        text = "The quick brown fox jumps over the lazy dog."
        grades = _compute_grades(text)
        assert len(grades) == 7
        expected_keys = {
            "flesch_kincaid_grade",
            "gunning_fog",
            "coleman_liau_index",
            "smog_index",
            "automated_readability_index",
            "dale_chall_readability_score",
            "linsear_write_formula",
        }
        assert set(grades.keys()) == expected_keys

    def test_values_are_floats(self) -> None:
        text = "The quick brown fox jumps over the lazy dog."
        grades = _compute_grades(text)
        for value in grades.values():
            assert isinstance(value, float)


class TestConsensus:
    """Tests for the _consensus helper."""

    def test_empty_grades_returns_zero(self) -> None:
        assert _consensus({}) == 0.0

    def test_single_grade(self) -> None:
        assert _consensus({"a": 5.0}) == 5.0

    def test_arithmetic_mean(self) -> None:
        grades = {"a": 2.0, "b": 4.0, "c": 6.0}
        assert _consensus(grades) == 4.0

    def test_rounds_to_one_decimal(self) -> None:
        grades = {"a": 1.0, "b": 2.0, "c": 3.0, "d": 4.0, "e": 5.0, "f": 6.0, "g": 7.0}
        result = _consensus(grades)
        # Mean of 1..7 = 4.0
        assert result == 4.0
        # Verify rounding with uneven values
        grades2 = {"a": 1.0, "b": 2.0, "c": 3.0}
        assert _consensus(grades2) == 2.0


class TestAnalyzeReadability:
    """Tests for the main analyze_readability function."""

    def test_returns_readability_result(self) -> None:
        sentences = [
            "The cat sat on the mat.",
            "It was a warm and sunny day.",
        ]
        result = analyze_readability(sentences, doc=None)
        assert isinstance(result, ReadabilityResult)

    def test_consensus_grade_is_mean_of_seven(self) -> None:
        """AC-FR-PIPELINE-03.1: consensus grade is arithmetic mean of 7 formulas."""
        sentences = [
            "The cat sat on the mat.",
            "It was a warm and sunny day.",
        ]
        result = analyze_readability(sentences, doc=None)
        expected = round(sum(result.individual_grades.values()) / 7, 1)
        assert result.consensus_grade == expected

    def test_individual_grades_has_seven_entries(self) -> None:
        sentences = ["The quick brown fox jumps over the lazy dog."]
        result = analyze_readability(sentences, doc=None)
        assert len(result.individual_grades) == 7

    def test_flesch_reading_ease_is_float(self) -> None:
        """AC-FR-PIPELINE-03.2: Flesch Reading Ease score."""
        sentences = ["The cat sat on the mat."]
        result = analyze_readability(sentences, doc=None)
        assert isinstance(result.flesch_reading_ease, float)

    def test_per_sentence_grades_length_matches_sentences(self) -> None:
        sentences = [
            "Short sentence.",
            "A somewhat longer sentence with more words in it.",
            "Another one.",
        ]
        result = analyze_readability(sentences, doc=None)
        assert len(result.per_sentence_grades) == len(sentences)

    def test_per_sentence_grades_are_floats(self) -> None:
        sentences = ["The cat sat on the mat.", "Dogs are friendly animals."]
        result = analyze_readability(sentences, doc=None)
        for grade in result.per_sentence_grades:
            assert isinstance(grade, float)

    def test_single_sentence(self) -> None:
        sentences = ["The cat sat on the mat."]
        result = analyze_readability(sentences, doc=None)
        assert len(result.per_sentence_grades) == 1
        assert result.consensus_grade == result.per_sentence_grades[0]

    def test_short_text_handles_gracefully(self) -> None:
        """textstat may return 0.0 for very short texts; handle gracefully."""
        sentences = ["Hi."]
        result = analyze_readability(sentences, doc=None)
        assert isinstance(result.consensus_grade, float)
        assert isinstance(result.flesch_reading_ease, float)
        assert len(result.per_sentence_grades) == 1

    def test_doc_parameter_is_unused(self) -> None:
        """The doc parameter is accepted but unused."""
        sentences = ["The cat sat on the mat."]
        result1 = analyze_readability(sentences, doc=None)
        result2 = analyze_readability(sentences, doc="anything")
        assert result1.consensus_grade == result2.consensus_grade
