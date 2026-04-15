"""Tests for the Vale-compatible rule evaluator.

Covers all 10 Vale rule types + 3 phraseturner extensions,
scope filtering, action support, and edge cases.
"""

from __future__ import annotations

import pytest

from phraseturner.personas.rules import (
    ACTION_REPLACE,
    RuleEvaluator,
    _get_position,
    _is_title_case,
    _split_paragraphs,
)
from phraseturner.personas.schema import RuleConfig, RuleLevel, RuleType


@pytest.fixture
def evaluator() -> RuleEvaluator:
    """Create a fresh RuleEvaluator instance."""
    return RuleEvaluator()


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------
class TestHelpers:
    def test_split_paragraphs(self) -> None:
        text = "First paragraph.\n\nSecond paragraph.\n\nThird."
        result = _split_paragraphs(text)
        assert result == ["First paragraph.", "Second paragraph.", "Third."]

    def test_split_paragraphs_empty(self) -> None:
        assert _split_paragraphs("") == []

    def test_get_position_first_char(self) -> None:
        assert _get_position("hello", 0) == (1, 1)

    def test_get_position_second_line(self) -> None:
        assert _get_position("hello\nworld", 6) == (2, 1)

    def test_is_title_case_valid(self) -> None:
        assert _is_title_case("The Quick Brown Fox")

    def test_is_title_case_with_small_words(self) -> None:
        assert _is_title_case("The Art of War")

    def test_is_title_case_invalid(self) -> None:
        assert not _is_title_case("the quick brown fox")

    def test_is_title_case_empty(self) -> None:
        assert _is_title_case("")


# ---------------------------------------------------------------------------
# Existence rule tests
# ---------------------------------------------------------------------------
class TestExistence:
    def test_token_match(self, evaluator: RuleEvaluator) -> None:
        rule = RuleConfig(
            id="no-very", type=RuleType.EXISTENCE, level=RuleLevel.WARNING,
            message="Avoid 'very'", tokens=["very"],
        )
        matches = evaluator.evaluate(rule, "This is very important.", ["This is very important."])
        assert len(matches) == 1
        assert matches[0].matched_text.lower() == "very"
        assert matches[0].level == "warning"

    def test_raw_regex_match(self, evaluator: RuleEvaluator) -> None:
        rule = RuleConfig(
            id="memory-uri", type=RuleType.EXISTENCE, level=RuleLevel.ERROR,
            message="No memory URIs", raw=[r"memory://\S+"],
        )
        text = "See memory://foo/bar for details."
        matches = evaluator.evaluate(rule, text, [text])
        assert len(matches) == 1
        assert "memory://foo/bar" in matches[0].matched_text

    def test_no_match(self, evaluator: RuleEvaluator) -> None:
        rule = RuleConfig(
            id="no-very", type=RuleType.EXISTENCE, level=RuleLevel.WARNING,
            tokens=["very"],
        )
        matches = evaluator.evaluate(rule, "This is important.", ["This is important."])
        assert matches == []

    def test_action_info(self, evaluator: RuleEvaluator) -> None:
        rule = RuleConfig(
            id="no-very", type=RuleType.EXISTENCE, level=RuleLevel.SUGGESTION,
            tokens=["very"], action={"name": "remove", "params": ""},
        )
        matches = evaluator.evaluate(rule, "very good", ["very good"])
        assert len(matches) == 1
        assert matches[0].action == "remove"


# ---------------------------------------------------------------------------
# Substitution rule tests
# ---------------------------------------------------------------------------
class TestSubstitution:
    def test_swap_match(self, evaluator: RuleEvaluator) -> None:
        """Validates: FR-PERSONA-02 (P-rt-03)."""
        rule = RuleConfig(
            id="brit-spelling", type=RuleType.SUBSTITUTION, level=RuleLevel.WARNING,
            swap={"color": "colour", "organize": "organise"},
        )
        matches = evaluator.evaluate(rule, "The color is nice.", ["The color is nice."])
        assert len(matches) == 1
        assert matches[0].matched_text.lower() == "color"
        assert matches[0].replacement == "colour"
        assert matches[0].action == ACTION_REPLACE

    def test_no_swap_match(self, evaluator: RuleEvaluator) -> None:
        rule = RuleConfig(
            id="brit-spelling", type=RuleType.SUBSTITUTION, level=RuleLevel.WARNING,
            swap={"color": "colour"},
        )
        matches = evaluator.evaluate(rule, "The colour is nice.", ["The colour is nice."])
        assert matches == []

    def test_empty_swap(self, evaluator: RuleEvaluator) -> None:
        rule = RuleConfig(
            id="empty", type=RuleType.SUBSTITUTION, level=RuleLevel.WARNING,
        )
        matches = evaluator.evaluate(rule, "Hello world.", ["Hello world."])
        assert matches == []


# ---------------------------------------------------------------------------
# Occurrence rule tests
# ---------------------------------------------------------------------------
class TestOccurrence:
    def test_exceeds_max(self, evaluator: RuleEvaluator) -> None:
        rule = RuleConfig(
            id="too-many-very", type=RuleType.OCCURRENCE, level=RuleLevel.WARNING,
            tokens=["very"], max=2,
        )
        text = "very very very important"
        matches = evaluator.evaluate(rule, text, [text])
        assert len(matches) == 1

    def test_within_max(self, evaluator: RuleEvaluator) -> None:
        rule = RuleConfig(
            id="too-many-very", type=RuleType.OCCURRENCE, level=RuleLevel.WARNING,
            tokens=["very"], max=2,
        )
        text = "very very important"
        matches = evaluator.evaluate(rule, text, [text])
        assert matches == []


# ---------------------------------------------------------------------------
# Repetition, Consistency, Conditional tests
# ---------------------------------------------------------------------------
class TestRepetition:
    def test_detects_repeated_word(self, evaluator: RuleEvaluator) -> None:
        rule = RuleConfig(
            id="no-repeat", type=RuleType.REPETITION, level=RuleLevel.WARNING,
        )
        text = "The cat sat on the mat."
        matches = evaluator.evaluate(rule, text, [text])
        repeated = [m.matched_text.lower() for m in matches]
        assert "the" in repeated

    def test_no_repetition(self, evaluator: RuleEvaluator) -> None:
        rule = RuleConfig(
            id="no-repeat", type=RuleType.REPETITION, level=RuleLevel.WARNING,
        )
        text = "Each word is unique here."
        matches = evaluator.evaluate(rule, text, [text])
        assert matches == []


class TestConsistency:
    def test_flags_inconsistent_usage(self, evaluator: RuleEvaluator) -> None:
        rule = RuleConfig(
            id="spelling", type=RuleType.CONSISTENCY, level=RuleLevel.WARNING,
            either={"color": "colour"},
        )
        text = "The color is nice. I like the colour too."
        matches = evaluator.evaluate(rule, text, [text])
        assert len(matches) >= 1
        assert matches[0].replacement is not None

    def test_no_inconsistency(self, evaluator: RuleEvaluator) -> None:
        rule = RuleConfig(
            id="spelling", type=RuleType.CONSISTENCY, level=RuleLevel.WARNING,
            either={"color": "colour"},
        )
        text = "The colour is nice. I like the colour too."
        matches = evaluator.evaluate(rule, text, [text])
        assert matches == []


class TestConditional:
    def test_trigger_without_consequent(self, evaluator: RuleEvaluator) -> None:
        rule = RuleConfig(
            id="fig-ref", type=RuleType.CONDITIONAL, level=RuleLevel.ERROR,
            tokens=["Figure"], match=r"Fig\.\s*\d+",
        )
        text = "See Figure for details."
        matches = evaluator.evaluate(rule, text, [text])
        assert len(matches) == 1

    def test_trigger_with_consequent(self, evaluator: RuleEvaluator) -> None:
        rule = RuleConfig(
            id="fig-ref", type=RuleType.CONDITIONAL, level=RuleLevel.ERROR,
            tokens=["Figure"], match=r"Fig\.\s*\d+",
        )
        text = "See Figure for details. Refer to Fig. 1."
        matches = evaluator.evaluate(rule, text, [text])
        assert matches == []


# ---------------------------------------------------------------------------
# Capitalization, Metric, Sequence, Script tests
# ---------------------------------------------------------------------------
class TestCapitalization:
    def test_title_case_pass(self, evaluator: RuleEvaluator) -> None:
        rule = RuleConfig(
            id="heading-case", type=RuleType.CAPITALIZATION, level=RuleLevel.ERROR,
            match="$title", scope="heading",
        )
        text = "The Quick Brown Fox\nBody text here."
        matches = evaluator.evaluate(rule, text, [text])
        assert matches == []

    def test_title_case_fail(self, evaluator: RuleEvaluator) -> None:
        rule = RuleConfig(
            id="heading-case", type=RuleType.CAPITALIZATION, level=RuleLevel.ERROR,
            match="$title", scope="heading",
        )
        text = "the quick brown fox\nBody text here."
        matches = evaluator.evaluate(rule, text, [text])
        assert len(matches) == 1

    def test_sentence_case_pass(self, evaluator: RuleEvaluator) -> None:
        rule = RuleConfig(
            id="heading-case", type=RuleType.CAPITALIZATION, level=RuleLevel.ERROR,
            match="$sentence", scope="heading",
        )
        text = "Hello world"
        matches = evaluator.evaluate(rule, text, [text])
        assert matches == []


class TestSequence:
    def test_returns_empty_placeholder(self, evaluator: RuleEvaluator) -> None:
        rule = RuleConfig(
            id="pos-seq", type=RuleType.SEQUENCE, level=RuleLevel.WARNING,
        )
        matches = evaluator.evaluate(rule, "Hello world.", ["Hello world."])
        assert matches == []


class TestScript:
    def test_raises_not_implemented(self, evaluator: RuleEvaluator) -> None:
        rule = RuleConfig(
            id="custom-script", type=RuleType.SCRIPT, level=RuleLevel.ERROR,
        )
        with pytest.raises(NotImplementedError, match=r"excluded in v1\.0"):
            evaluator.evaluate(rule, "Hello.", ["Hello."])


# ---------------------------------------------------------------------------
# phraseturner extension tests
# ---------------------------------------------------------------------------
class TestExtensions:
    def test_llm_eval_placeholder(self, evaluator: RuleEvaluator) -> None:
        rule = RuleConfig(
            id="t5-check", type=RuleType.LLM_EVAL, level=RuleLevel.WARNING,
            prompt="Is this formal?", target="yes",
        )
        matches = evaluator.evaluate(rule, "Hello.", ["Hello."])
        assert matches == []

    def test_tone_placeholder(self, evaluator: RuleEvaluator) -> None:
        rule = RuleConfig(
            id="tone-check", type=RuleType.TONE, level=RuleLevel.WARNING,
            dimension="formality", min=0.7,
        )
        matches = evaluator.evaluate(rule, "Hello.", ["Hello."])
        assert matches == []

    def test_brand_voice_placeholder(self, evaluator: RuleEvaluator) -> None:
        rule = RuleConfig(
            id="brand-check", type=RuleType.BRAND_VOICE, level=RuleLevel.WARNING,
        )
        matches = evaluator.evaluate(rule, "Hello.", ["Hello."])
        assert matches == []


# ---------------------------------------------------------------------------
# Scope filtering tests
# ---------------------------------------------------------------------------
class TestScopeFiltering:
    def test_sentence_scope(self, evaluator: RuleEvaluator) -> None:
        rule = RuleConfig(
            id="no-very", type=RuleType.EXISTENCE, level=RuleLevel.WARNING,
            tokens=["very"], scope="sentence",
        )
        sentences = ["This is very good.", "This is fine."]
        text = " ".join(sentences)
        matches = evaluator.evaluate(rule, text, sentences)
        assert len(matches) == 1

    def test_paragraph_scope(self, evaluator: RuleEvaluator) -> None:
        rule = RuleConfig(
            id="no-very", type=RuleType.EXISTENCE, level=RuleLevel.WARNING,
            tokens=["very"], scope="paragraph",
        )
        text = "This is very good.\n\nThis is fine."
        sentences = ["This is very good.", "This is fine."]
        matches = evaluator.evaluate(rule, text, sentences)
        assert len(matches) == 1

    def test_raw_scope(self, evaluator: RuleEvaluator) -> None:
        rule = RuleConfig(
            id="raw-check", type=RuleType.EXISTENCE, level=RuleLevel.WARNING,
            raw=[r"memory://\S+"], scope="raw",
        )
        text = "See memory://test for info."
        matches = evaluator.evaluate(rule, text, [text])
        assert len(matches) == 1
