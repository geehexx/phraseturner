"""Unit tests for Stage 0: input validation and sentence splitting.

Tests cover:
- Empty/whitespace rejection (TextTooShortError)
- Token limit enforcement (TextTooLongError)
- Sentence splitting via spaCy
- Token counting (non-whitespace tokens)
- Tier 0 fallback (no spaCy)
"""

from __future__ import annotations

import pytest
import spacy

from phraseturner.config import ServerConfig
from phraseturner.exceptions import TextTooLongError, TextTooShortError
from phraseturner.pipeline.stage0 import (
    Stage0Result,
    _fallback_split_sentences,
    _fallback_token_count,
    run_stage0,
)


@pytest.fixture(scope="module")
def nlp() -> spacy.language.Language:
    """Load spaCy model once for the test module."""
    return spacy.load("en_core_web_sm")


@pytest.fixture()
def config() -> ServerConfig:
    """Default server config."""
    return ServerConfig()


@pytest.fixture()
def small_config() -> ServerConfig:
    """Config with a very low token limit for testing."""
    return ServerConfig(max_tokens=5)


# ---------------------------------------------------------------------------
# TextTooShortError tests
# ---------------------------------------------------------------------------


class TestEmptyInput:
    """Reject empty or whitespace-only input."""

    @pytest.mark.asyncio
    async def test_empty_string(self, nlp: spacy.language.Language, config: ServerConfig) -> None:
        with pytest.raises(TextTooShortError):
            await run_stage0("", nlp, config)

    @pytest.mark.asyncio
    async def test_whitespace_only(
        self, nlp: spacy.language.Language, config: ServerConfig
    ) -> None:
        with pytest.raises(TextTooShortError):
            await run_stage0("   \t\n  ", nlp, config)

    @pytest.mark.asyncio
    async def test_empty_no_spacy(self, config: ServerConfig) -> None:
        with pytest.raises(TextTooShortError):
            await run_stage0("", None, config)


# ---------------------------------------------------------------------------
# TextTooLongError tests
# ---------------------------------------------------------------------------


class TestTokenLimit:
    """Reject text exceeding the token limit."""

    @pytest.mark.asyncio
    async def test_exceeds_limit_spacy(
        self, nlp: spacy.language.Language, small_config: ServerConfig
    ) -> None:
        text = "one two three four five six seven eight nine ten"
        with pytest.raises(TextTooLongError) as exc_info:
            await run_stage0(text, nlp, small_config)
        assert exc_info.value.details is not None
        assert exc_info.value.details["max_tokens"] == 5

    @pytest.mark.asyncio
    async def test_exceeds_limit_fallback(self, small_config: ServerConfig) -> None:
        text = "one two three four five six seven eight nine ten"
        with pytest.raises(TextTooLongError) as exc_info:
            await run_stage0(text, None, small_config)
        assert exc_info.value.details is not None
        assert exc_info.value.details["max_tokens"] == 5

    @pytest.mark.asyncio
    async def test_at_limit_passes(
        self, nlp: spacy.language.Language, small_config: ServerConfig
    ) -> None:
        """Text with exactly max_tokens should pass."""
        text = "one two three four five"
        result = await run_stage0(text, nlp, small_config)
        assert result.token_count == 5


# ---------------------------------------------------------------------------
# Sentence splitting tests
# ---------------------------------------------------------------------------


class TestSentenceSplitting:
    """Verify sentence splitting via spaCy."""

    @pytest.mark.asyncio
    async def test_single_sentence(
        self, nlp: spacy.language.Language, config: ServerConfig
    ) -> None:
        result = await run_stage0("Hello world.", nlp, config)
        assert len(result.sentences) == 1
        assert result.sentences[0].strip() == "Hello world."

    @pytest.mark.asyncio
    async def test_multiple_sentences(
        self, nlp: spacy.language.Language, config: ServerConfig
    ) -> None:
        text = "First sentence. Second sentence. Third sentence."
        result = await run_stage0(text, nlp, config)
        assert len(result.sentences) == 3

    @pytest.mark.asyncio
    async def test_doc_is_returned(
        self, nlp: spacy.language.Language, config: ServerConfig
    ) -> None:
        result = await run_stage0("Hello world.", nlp, config)
        assert result.doc is not None


# ---------------------------------------------------------------------------
# Token counting tests
# ---------------------------------------------------------------------------


class TestTokenCounting:
    """Verify non-whitespace token counting."""

    @pytest.mark.asyncio
    async def test_token_count_matches_spacy(
        self, nlp: spacy.language.Language, config: ServerConfig
    ) -> None:
        text = "The quick brown fox jumps."
        result = await run_stage0(text, nlp, config)
        # Verify against direct spaCy count
        doc = nlp(text)
        expected = sum(1 for tok in doc if not tok.is_space)
        assert result.token_count == expected


# ---------------------------------------------------------------------------
# Tier 0 fallback tests
# ---------------------------------------------------------------------------


class TestFallback:
    """Tier 0 fallback when spaCy is unavailable."""

    @pytest.mark.asyncio
    async def test_fallback_returns_result(self, config: ServerConfig) -> None:
        result = await run_stage0("Hello world. How are you?", None, config)
        assert isinstance(result, Stage0Result)
        assert result.doc is None
        assert len(result.sentences) >= 1
        assert result.token_count > 0

    @pytest.mark.asyncio
    async def test_fallback_sentence_split(self, config: ServerConfig) -> None:
        result = await run_stage0("First. Second! Third?", None, config)
        assert len(result.sentences) == 3

    def test_fallback_split_helper(self) -> None:
        assert _fallback_split_sentences("A. B! C?") == ["A.", "B!", "C?"]

    def test_fallback_count_helper(self) -> None:
        assert _fallback_token_count("one two three") == 3
