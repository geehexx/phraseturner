"""Tests for the structured context builder, 512-token handling, and T5Runner.

Tests: SentenceContext, build_context, format_context_string, truncate_for_t5,
and T5Runner initialisation.

Validates: FR-T5-05, FR-T5-07
Design: §5.3, §5.6, §5.7
"""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import MagicMock

import pytest

from phraseturner.t5.context import (
    SentenceContext,
    T5Runner,
    _classify_length,
    _estimate_subword_tokens,
    _truncate_to_tokens,
    _vader_compound_to_label,
    build_context,
    format_context_string,
    truncate_for_t5,
)

# ---------------------------------------------------------------------------
# Fixtures — lightweight persona stubs
# ---------------------------------------------------------------------------


@dataclass
class _StubTone:
    formality: float = 0.3
    confidence: float = 0.7
    warmth: float = 0.8
    directness: float = 0.6
    energy: float = 0.5
    verbosity: float = 0.4


@dataclass
class _StubVocabulary:
    approved: list[str] = field(default_factory=lambda: ["clear", "simple"])
    prohibited: list[str] = field(
        default_factory=lambda: ["furthermore", "aforementioned"],
    )


@dataclass
class _StubPersona:
    tone: _StubTone = field(default_factory=_StubTone)
    vocabulary: _StubVocabulary = field(default_factory=_StubVocabulary)


# ---------------------------------------------------------------------------
# _truncate_to_tokens
# ---------------------------------------------------------------------------


class TestTruncateToTokens:
    """Tests for the _truncate_to_tokens helper."""

    def test_short_text_unchanged(self) -> None:
        text = "hello world"
        assert _truncate_to_tokens(text, 30) == text

    def test_exact_limit_unchanged(self) -> None:
        text = "one two three"
        assert _truncate_to_tokens(text, 3) == text

    def test_truncates_long_text(self) -> None:
        text = "one two three four five six"
        result = _truncate_to_tokens(text, 3)
        assert result == "one two three"

    def test_empty_text(self) -> None:
        assert _truncate_to_tokens("", 30) == ""


# ---------------------------------------------------------------------------
# _classify_length
# ---------------------------------------------------------------------------


class TestClassifyLength:
    """Tests for sentence length classification."""

    def test_short_sentence(self) -> None:
        assert _classify_length("Hello world.") == "short"

    def test_medium_sentence(self) -> None:
        sentence = " ".join(["word"] * 15)
        assert _classify_length(sentence) == "medium"

    def test_long_sentence(self) -> None:
        sentence = " ".join(["word"] * 30)
        assert _classify_length(sentence) == "long"

    def test_boundary_short_medium(self) -> None:
        # 9 tokens = short, 10 tokens = medium
        assert _classify_length(" ".join(["w"] * 9)) == "short"
        assert _classify_length(" ".join(["w"] * 10)) == "medium"

    def test_boundary_medium_long(self) -> None:
        # 25 tokens = medium, 26 tokens = long
        assert _classify_length(" ".join(["w"] * 25)) == "medium"
        assert _classify_length(" ".join(["w"] * 26)) == "long"


# ---------------------------------------------------------------------------
# _vader_compound_to_label
# ---------------------------------------------------------------------------


class TestVaderCompoundToLabel:
    """Tests for VADER compound to label mapping."""

    def test_positive(self) -> None:
        assert _vader_compound_to_label(0.5) == "positive"
        assert _vader_compound_to_label(0.06) == "positive"

    def test_negative(self) -> None:
        assert _vader_compound_to_label(-0.5) == "negative"
        assert _vader_compound_to_label(-0.06) == "negative"

    def test_neutral(self) -> None:
        assert _vader_compound_to_label(0.0) == "neutral"
        assert _vader_compound_to_label(0.05) == "neutral"
        assert _vader_compound_to_label(-0.05) == "neutral"


# ---------------------------------------------------------------------------
# _estimate_subword_tokens
# ---------------------------------------------------------------------------


class TestEstimateSubwordTokens:
    """Tests for subword token estimation."""

    def test_empty_string(self) -> None:
        assert _estimate_subword_tokens("") == 0

    def test_single_word(self) -> None:
        result = _estimate_subword_tokens("hello")
        assert result == 2  # ceil(1 * 1.3) = 2

    def test_multiple_words(self) -> None:
        result = _estimate_subword_tokens("hello world foo")
        assert result == 4  # ceil(3 * 1.3) = 4


# ---------------------------------------------------------------------------
# build_context
# ---------------------------------------------------------------------------


class TestBuildContext:
    """Tests for the build_context function."""

    def test_basic_context_no_extras(self) -> None:
        sentences = ["First sentence.", "Second sentence.", "Third sentence."]
        ctx = build_context(1, sentences)

        assert ctx.prev_sentence == "First sentence."
        assert ctx.next_sentence == "Third sentence."
        assert ctx.readability_grade is None
        assert ctx.length_class == "short"
        assert ctx.vader_label is None
        assert ctx.ai_signal is None
        assert ctx.persona_tone is None
        assert ctx.avoid_hits == []
        assert ctx.prefer_hits == []

    def test_first_sentence_no_prev(self) -> None:
        sentences = ["Only sentence.", "Next one."]
        ctx = build_context(0, sentences)
        assert ctx.prev_sentence is None
        assert ctx.next_sentence == "Next one."

    def test_last_sentence_no_next(self) -> None:
        sentences = ["Prev one.", "Last sentence."]
        ctx = build_context(1, sentences)
        assert ctx.prev_sentence == "Prev one."
        assert ctx.next_sentence is None

    def test_single_sentence(self) -> None:
        sentences = ["Alone."]
        ctx = build_context(0, sentences)
        assert ctx.prev_sentence is None
        assert ctx.next_sentence is None

    def test_prev_sentence_truncated(self) -> None:
        long_prev = " ".join(["word"] * 50)
        sentences = [long_prev, "Target sentence."]
        ctx = build_context(1, sentences)
        assert ctx.prev_sentence is not None
        assert len(ctx.prev_sentence.split()) == 30

    def test_readability_grades(self) -> None:
        sentences = ["Sentence one.", "Sentence two."]
        ctx = build_context(0, sentences, readability_grades=[8.5, 12.0])
        assert ctx.readability_grade == 8.5

    def test_vader_compounds(self) -> None:
        sentences = ["Happy sentence!", "Sad sentence."]
        ctx = build_context(0, sentences, vader_compounds=[0.8, -0.6])
        assert ctx.vader_label == "positive"

    def test_ai_signal(self) -> None:
        sentences = ["Some text."]
        ctx = build_context(0, sentences, ai_signal="likely-ai")
        assert ctx.ai_signal == "likely-ai"

    def test_persona_tone_extraction(self) -> None:
        sentences = ["Some text."]
        persona = _StubPersona()
        ctx = build_context(0, sentences, persona=persona)

        assert ctx.persona_tone is not None
        assert ctx.persona_tone["formality"] == 0.3
        assert ctx.persona_tone["warmth"] == 0.8

    def test_persona_vocabulary_hits(self) -> None:
        sentences = ["Furthermore, this is a clear and simple explanation."]
        persona = _StubPersona()
        ctx = build_context(0, sentences, persona=persona)

        assert "furthermore" in ctx.avoid_hits
        assert "clear" in ctx.prefer_hits
        assert "simple" in ctx.prefer_hits

    def test_persona_no_vocabulary_hits(self) -> None:
        sentences = ["The dog ran quickly."]
        persona = _StubPersona()
        ctx = build_context(0, sentences, persona=persona)

        assert ctx.avoid_hits == []
        assert ctx.prefer_hits == []


# ---------------------------------------------------------------------------
# format_context_string
# ---------------------------------------------------------------------------


class TestFormatContextString:
    """Tests for the format_context_string function."""

    def test_minimal_context(self) -> None:
        ctx = SentenceContext(length_class="short")
        result = format_context_string(ctx)
        assert "length: short" in result

    def test_full_context(self) -> None:
        ctx = SentenceContext(
            prev_sentence="Previous text here.",
            next_sentence="Next text here.",
            readability_grade=8.5,
            length_class="medium",
            vader_label="positive",
            ai_signal="likely-human",
            persona_tone={"formality": 0.3, "warmth": 0.8},
            avoid_hits=["furthermore"],
            prefer_hits=["clear"],
        )
        result = format_context_string(ctx)

        assert "prev: Previous text here." in result
        assert "next: Next text here." in result
        assert "grade: 8.5" in result
        assert "length: medium" in result
        assert "sentiment: positive" in result
        assert "ai: likely-human" in result
        assert "tone:" in result
        assert "formality=0.3" in result
        assert "avoid: furthermore" in result
        assert "prefer: clear" in result

    def test_pipe_separated(self) -> None:
        ctx = SentenceContext(
            readability_grade=10.0,
            length_class="long",
            vader_label="negative",
        )
        result = format_context_string(ctx)
        assert " | " in result

    def test_avoid_hits_capped_at_5(self) -> None:
        ctx = SentenceContext(
            avoid_hits=["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf"],
        )
        result = format_context_string(ctx)
        # Should only include first 5
        assert "foxtrot" not in result
        assert "golf" not in result


# ---------------------------------------------------------------------------
# truncate_for_t5
# ---------------------------------------------------------------------------


class TestTruncateForT5:
    """Tests for the truncate_for_t5 function."""

    def test_short_sentence_not_truncated(self) -> None:
        sentence = "Hello world."
        context = "length: short"
        result, truncated = truncate_for_t5(sentence, context)
        assert result == sentence
        assert truncated is False

    def test_long_sentence_truncated(self) -> None:
        # Create a sentence that with context exceeds 512 tokens
        sentence = " ".join(["word"] * 500)
        context = "length: long | sentiment: positive"
        result, truncated = truncate_for_t5(sentence, context)
        assert truncated is True
        assert len(result.split()) < 500

    def test_preserves_beginning(self) -> None:
        """AC-FR-T5-07.2: Truncation preserves the beginning."""
        sentence = "alpha beta gamma delta epsilon zeta eta theta " * 50
        context = "length: long | grade: 12.0"
        result, truncated = truncate_for_t5(sentence, context)
        assert truncated is True
        assert result.startswith("alpha beta gamma")

    def test_empty_context(self) -> None:
        sentence = "Short sentence."
        result, truncated = truncate_for_t5(sentence, "")
        assert result == sentence
        assert truncated is False

    def test_custom_max_tokens(self) -> None:
        sentence = " ".join(["word"] * 100)
        context = "length: medium"
        result, truncated = truncate_for_t5(sentence, context, max_tokens=50)
        assert truncated is True
        assert len(result.split()) < 100

    def test_context_alone_exceeds_budget(self) -> None:
        sentence = "hello world"
        context = " ".join(["ctx"] * 500)
        _result, truncated = truncate_for_t5(sentence, context, max_tokens=10)
        assert truncated is True


# ---------------------------------------------------------------------------
# T5Runner
# ---------------------------------------------------------------------------


class TestT5Runner:
    """Tests for T5Runner initialisation and cleanup."""

    def test_init_unpacks_sessions(self) -> None:
        encoder = MagicMock()
        decoder = MagicMock()
        tokenizer = MagicMock()

        runner = T5Runner(session=(encoder, decoder), tokenizer=tokenizer)

        assert runner._encoder_session is encoder
        assert runner._decoder_session is decoder
        assert runner._tokenizer is tokenizer

    def test_executor_max_workers_one(self) -> None:
        """Verify ThreadPoolExecutor(max_workers=1) per ONNX bug #21053."""
        encoder = MagicMock()
        decoder = MagicMock()
        tokenizer = MagicMock()

        runner = T5Runner(session=(encoder, decoder), tokenizer=tokenizer)
        assert runner._executor._max_workers == 1

    @pytest.mark.asyncio()
    async def test_cleanup_shuts_down_executor(self) -> None:
        encoder = MagicMock()
        decoder = MagicMock()
        tokenizer = MagicMock()

        runner = T5Runner(session=(encoder, decoder), tokenizer=tokenizer)
        await runner.cleanup()
        # After shutdown, the executor should not accept new tasks
        assert runner._executor._shutdown


# ---------------------------------------------------------------------------
# SentenceContext dataclass
# ---------------------------------------------------------------------------


class TestSentenceContext:
    """Tests for the SentenceContext dataclass."""

    def test_defaults(self) -> None:
        ctx = SentenceContext()
        assert ctx.prev_sentence is None
        assert ctx.next_sentence is None
        assert ctx.readability_grade is None
        assert ctx.length_class == "medium"
        assert ctx.vader_label is None
        assert ctx.ai_signal is None
        assert ctx.persona_tone is None
        assert ctx.avoid_hits == []
        assert ctx.prefer_hits == []

    def test_frozen(self) -> None:
        ctx = SentenceContext()
        with pytest.raises(AttributeError):
            ctx.length_class = "long"  # type: ignore[misc]
