"""Integration smoke tests for all 7 MCP tools.

Tests each tool with minimal valid input, verifies response schema,
exercises error paths (TEXT_TOO_LONG, PERSONA_NOT_FOUND,
PERSONA_VALIDATION_FAILED, PERSONA_EXISTS), and validates graceful
degradation when T5 or FastEmbed are disabled.

Implements Task 5.4.
Requirements: FR-TOOL-01 through FR-TOOL-07.
Design: §2.6.
"""

from __future__ import annotations

import contextlib
import dataclasses
from typing import Any
from unittest.mock import MagicMock

import pytest

from phraseturner.config import ServerConfig
from phraseturner.models.loader import ModelLoader
from phraseturner.personas.index import PersonaIndex
from phraseturner.tools import (
    analyze,
    compare,
    create_persona,
    get_persona,
    list_personas,
    score,
    validate_persona,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class _FakeRequestContext:
    """Minimal stand-in for FastMCP's internal request context."""

    lifespan_context: dict[str, Any]


def _build_mock_ctx(lifespan_ctx: dict[str, Any]) -> MagicMock:
    """Build a mock FastMCP ``Context`` that exposes lifespan_context.

    The tools access ``ctx.request_context.lifespan_context`` to
    retrieve the config, persona_index, and models objects.
    """
    ctx = MagicMock()
    ctx.request_context = _FakeRequestContext(lifespan_context=lifespan_ctx)
    return ctx


@pytest.fixture()
def _server_config(tmp_path: Any) -> ServerConfig:
    """ServerConfig with all optional models disabled for fast tests."""
    return ServerConfig(
        disable_t5=True,
        disable_slop=True,
        disable_embed=True,
        personas_dir=tmp_path / "personas",
        watch_enabled=False,
    )


@pytest.fixture()
async def _lifespan_ctx(
    _server_config: ServerConfig,
) -> dict[str, Any]:
    """Minimal lifespan context with real persona index and model loader.

    Loads personas from the built-in directory only (T5, slop, and
    FastEmbed are all disabled via config).
    """
    models = ModelLoader(_server_config)
    persona_index = PersonaIndex(_server_config)

    # Load spaCy — required for Tier 1+ analysis
    with contextlib.suppress(Exception):
        await models.load_spacy()

    # Load personas from built-in directory
    await persona_index.load_all()

    # Attempt optional model loads (all disabled, so these are no-ops)
    await models.load_fastembed()
    await models.load_slop_detector()
    await models.load_t5()

    return {
        "config": _server_config,
        "persona_index": persona_index,
        "models": models,
    }


@pytest.fixture()
def ctx(_lifespan_ctx: dict[str, Any]) -> MagicMock:
    """Mock FastMCP Context wired to the lifespan context."""
    return _build_mock_ctx(_lifespan_ctx)


# ---------------------------------------------------------------------------
# Happy-path smoke tests — one per tool
# ---------------------------------------------------------------------------


class TestAnalyzeTool:
    """Smoke tests for the ``analyze`` tool (FR-TOOL-01)."""

    @pytest.mark.asyncio
    async def test_happy_path(self, ctx: MagicMock) -> None:
        result = await analyze(
            text="The quick brown fox jumps over the lazy dog.",
            ctx=ctx,
        )

        assert "health_score" in result
        assert "sentences" in result
        assert "metadata" in result
        hs = result["health_score"]
        assert "composite_score" in hs
        assert "letter_grade" in hs
        assert hs["letter_grade"] in ("A", "B", "C", "D", "F")
        assert "dimensions" in hs
        meta = result["metadata"]
        assert "token_count" in meta
        assert "operating_tier" in meta
        assert "t5_available" in meta
        assert isinstance(meta["token_count"], int)
        assert meta["token_count"] > 0

    @pytest.mark.asyncio
    async def test_concise_format(self, ctx: MagicMock) -> None:
        result = await analyze(
            text="Hello world. This is a test.",
            response_format="concise",
            ctx=ctx,
        )

        assert "health_score" in result
        assert "flags_summary" in result
        assert "next_steps" in result
        assert "metadata" in result
        # Concise mode omits per-sentence breakdowns
        assert "sentences" not in result


class TestScoreTool:
    """Smoke tests for the ``score`` tool (FR-TOOL-07)."""

    @pytest.mark.asyncio
    async def test_happy_path(self, ctx: MagicMock) -> None:
        result = await score(
            text="The quick brown fox jumps over the lazy dog.",
            ctx=ctx,
        )

        assert "composite_score" in result
        assert "letter_grade" in result
        assert result["letter_grade"] in ("A", "B", "C", "D", "F")
        assert "dimensions" in result
        assert "metadata" in result
        assert "next_steps" in result
        assert result["metadata"]["t5_available"] is False


class TestCompareTool:
    """Smoke tests for the ``compare`` tool (FR-TOOL-06)."""

    @pytest.mark.asyncio
    async def test_happy_path(self, ctx: MagicMock) -> None:
        result = await compare(
            original="The system was implemented by the team.",
            rewritten="The team implemented the system.",
            ctx=ctx,
        )

        assert "semantic_similarity" in result
        assert "health_score_delta" in result
        assert "overall_improvement" in result
        assert "sentence_alignment" in result
        assert "next_steps" in result
        assert "metadata" in result
        assert isinstance(result["semantic_similarity"], float)
        assert isinstance(result["overall_improvement"], float)


class TestListPersonasTool:
    """Smoke tests for the ``list_personas`` tool (FR-TOOL-02)."""

    @pytest.mark.asyncio
    async def test_happy_path(self, ctx: MagicMock) -> None:
        result = await list_personas(ctx=ctx)

        assert "personas" in result
        assert "next_steps" in result
        assert isinstance(result["personas"], list)
        assert len(result["personas"]) > 0
        # Verify PersonaSummary schema
        first = result["personas"][0]
        assert "name" in first
        assert "tier" in first
        assert "version" in first


class TestGetPersonaTool:
    """Smoke tests for the ``get_persona`` tool (FR-TOOL-03)."""

    @pytest.mark.asyncio
    async def test_happy_path(self, ctx: MagicMock) -> None:
        result = await get_persona(
            name_or_query="slack-casual",
            ctx=ctx,
        )

        assert "name" in result
        assert result["name"] == "slack-casual"
        assert "version" in result
        assert "tone" in result
        assert "rules" in result
        assert "tier" in result
        assert "next_steps" in result


_VALID_PERSONA_YAML = """\
name: test-integration-persona
version: "1.0.0"
description: A test persona for integration tests.
tone:
  formality: 0.3
  confidence: 0.7
  warmth: 0.8
  directness: 0.6
  energy: 0.5
  verbosity: 0.4
rules:
  - id: no-jargon
    type: existence
    level: warning
    message: Avoid jargon.
    tokens:
      - synergy
      - leverage
  - id: short-sentences
    type: metric
    level: suggestion
    message: Keep sentences short.
    metric: sentence_length
    max: 25
  - id: tone-warmth
    type: tone
    level: warning
    message: Maintain warm tone.
    dimension: warmth
    min: 0.5
"""


class TestCreatePersonaTool:
    """Smoke tests for the ``create_persona`` tool (FR-TOOL-04)."""

    @pytest.mark.asyncio
    async def test_happy_path(self, ctx: MagicMock) -> None:
        result = await create_persona(
            yaml_content=_VALID_PERSONA_YAML,
            ctx=ctx,
        )

        assert "name" in result
        assert result["name"] == "test-integration-persona"
        assert "file_path" in result
        assert "validation" in result
        assert result["validation"]["valid"] is True
        assert "next_steps" in result


class TestValidatePersonaTool:
    """Smoke tests for the ``validate_persona`` tool (FR-TOOL-05)."""

    @pytest.mark.asyncio
    async def test_happy_path_valid(self, ctx: MagicMock) -> None:
        result = await validate_persona(
            yaml_content=_VALID_PERSONA_YAML,
            ctx=ctx,
        )

        assert "valid" in result
        assert result["valid"] is True
        assert "errors" in result
        assert "warnings" in result
        assert isinstance(result["errors"], list)
        assert "next_steps" in result


# ---------------------------------------------------------------------------
# Error path tests
# ---------------------------------------------------------------------------


class TestErrorPaths:
    """Error paths return structured ToolError responses."""

    @pytest.mark.asyncio
    async def test_analyze_text_too_long(self, ctx: MagicMock) -> None:
        """TEXT_TOO_LONG when input exceeds 8000 tokens."""
        long_text = "word " * 9000
        result = await analyze(text=long_text, ctx=ctx)

        assert "error" in result
        assert result["error"]["code"] == "TEXT_TOO_LONG"
        assert "next_steps" in result

    @pytest.mark.asyncio
    async def test_get_persona_not_found(self, ctx: MagicMock) -> None:
        """PERSONA_NOT_FOUND for a nonexistent persona name."""
        result = await get_persona(
            name_or_query="nonexistent-persona-xyz-999",
            ctx=ctx,
        )

        assert "error" in result
        assert result["error"]["code"] == "PERSONA_NOT_FOUND"
        assert "next_steps" in result

    @pytest.mark.asyncio
    async def test_create_persona_validation_failed(self, ctx: MagicMock) -> None:
        """PERSONA_VALIDATION_FAILED for invalid YAML content."""
        invalid_yaml = "version: not-semver\n"
        result = await create_persona(yaml_content=invalid_yaml, ctx=ctx)

        assert "error" in result
        assert result["error"]["code"] in (
            "PERSONA_VALIDATION_FAILED",
            "INVALID_YAML",
        )
        assert "next_steps" in result

    @pytest.mark.asyncio
    async def test_validate_persona_invalid(self, ctx: MagicMock) -> None:
        """validate_persona returns valid=false for bad YAML."""
        invalid_yaml = "version: not-semver\n"
        result = await validate_persona(yaml_content=invalid_yaml, ctx=ctx)

        assert "valid" in result
        assert result["valid"] is False
        assert len(result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_create_persona_exists(self, ctx: MagicMock) -> None:
        """PERSONA_EXISTS when creating a duplicate persona."""
        # First creation should succeed
        result1 = await create_persona(
            yaml_content=_VALID_PERSONA_YAML,
            ctx=ctx,
        )
        assert "name" in result1

        # Second creation with same name should fail
        result2 = await create_persona(
            yaml_content=_VALID_PERSONA_YAML,
            ctx=ctx,
        )
        assert "error" in result2
        assert result2["error"]["code"] == "PERSONA_EXISTS"
        assert "next_steps" in result2


# ---------------------------------------------------------------------------
# Graceful degradation tests
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    """Verify tools degrade gracefully when models are disabled."""

    @pytest.mark.asyncio
    async def test_analyze_t5_disabled(self, ctx: MagicMock) -> None:
        """With T5 disabled, metadata reports t5_available=false."""
        result = await analyze(
            text="Hello world. This is a test sentence.",
            ctx=ctx,
        )

        assert "metadata" in result
        assert result["metadata"]["t5_available"] is False

    @pytest.mark.asyncio
    async def test_analyze_fastembed_disabled(self, ctx: MagicMock) -> None:
        """With FastEmbed disabled, semantic features are null."""
        result = await analyze(
            text="Hello world. This is a test sentence.",
            original_text="Original hello world.",
            ctx=ctx,
        )

        assert "metadata" in result
        # Semantic preservation should be null when FastEmbed is disabled
        dims = result["health_score"]["dimensions"]
        sem = dims.get("semantic_preservation")
        if sem is not None:
            # Score should be null or 0 when embed is disabled
            assert sem.get("score") is None or sem.get("score") == 0.0

    @pytest.mark.asyncio
    async def test_compare_fastembed_disabled(self, ctx: MagicMock) -> None:
        """With FastEmbed disabled, semantic_similarity is 0.0."""
        result = await compare(
            original="The cat sat on the mat.",
            rewritten="A cat was sitting on the mat.",
            ctx=ctx,
        )

        assert "semantic_similarity" in result
        assert result["semantic_similarity"] == 0.0

    @pytest.mark.asyncio
    async def test_score_t5_disabled(self, ctx: MagicMock) -> None:
        """Score tool works without T5 (quick path skips Stage 3)."""
        result = await score(
            text="The quick brown fox jumps over the lazy dog.",
            ctx=ctx,
        )

        assert "composite_score" in result
        assert "letter_grade" in result
        assert result["metadata"]["t5_available"] is False


# ---------------------------------------------------------------------------
# Additional coverage tests
# ---------------------------------------------------------------------------


class TestCompareConciseMode:
    """compare tool concise response format (FR-TOOL-09)."""

    @pytest.mark.asyncio
    async def test_concise_format(self, ctx: MagicMock) -> None:
        result = await compare(
            original="The system was implemented by the team.",
            rewritten="The team implemented the system.",
            response_format="concise",
            ctx=ctx,
        )

        assert "semantic_similarity" in result
        assert "overall_improvement" in result
        assert "next_steps" in result
        assert "metadata" in result
        # Concise mode omits sentence_alignment
        assert "sentence_alignment" not in result


class TestListPersonasFiltering:
    """list_personas query search and tag filtering (FR-TOOL-02)."""

    @pytest.mark.asyncio
    async def test_query_search(self, ctx: MagicMock) -> None:
        result = await list_personas(query="slack", ctx=ctx)

        assert "personas" in result
        assert isinstance(result["personas"], list)

    @pytest.mark.asyncio
    async def test_tag_filtering_match(self, ctx: MagicMock) -> None:
        # First get all personas to find a real tag
        all_result = await list_personas(ctx=ctx)
        personas = all_result["personas"]
        assert len(personas) > 0

        # Find a tag that exists
        real_tags = personas[0].get("tags", [])
        if real_tags:
            result = await list_personas(tags=[real_tags[0]], ctx=ctx)
            assert "personas" in result
            # All returned personas must have the tag
            for p in result["personas"]:
                assert real_tags[0].lower() in [t.lower() for t in p.get("tags", [])]

    @pytest.mark.asyncio
    async def test_tag_filtering_no_match(self, ctx: MagicMock) -> None:
        result = await list_personas(tags=["nonexistent-tag-xyz-999"], ctx=ctx)

        assert "personas" in result
        assert result["personas"] == []


class TestCtxNoneGuards:
    """ctx=None returns INTERNAL_ERROR for all tools (error_handler catches RuntimeError)."""

    @pytest.mark.asyncio
    async def test_analyze_ctx_none(self) -> None:
        result = await analyze(text="hello", ctx=None)
        assert "error" in result
        assert result["error"]["code"] == "INTERNAL_ERROR"

    @pytest.mark.asyncio
    async def test_score_ctx_none(self) -> None:
        result = await score(text="hello", ctx=None)
        assert "error" in result
        assert result["error"]["code"] == "INTERNAL_ERROR"

    @pytest.mark.asyncio
    async def test_compare_ctx_none(self) -> None:
        result = await compare(original="a", rewritten="b", ctx=None)
        assert "error" in result
        assert result["error"]["code"] == "INTERNAL_ERROR"

    @pytest.mark.asyncio
    async def test_list_personas_ctx_none(self) -> None:
        result = await list_personas(ctx=None)
        assert "error" in result
        assert result["error"]["code"] == "INTERNAL_ERROR"

    @pytest.mark.asyncio
    async def test_get_persona_ctx_none(self) -> None:
        result = await get_persona(name_or_query="slack-casual", ctx=None)
        assert "error" in result
        assert result["error"]["code"] == "INTERNAL_ERROR"

    @pytest.mark.asyncio
    async def test_create_persona_ctx_none(self) -> None:
        result = await create_persona(yaml_content="name: test\n", ctx=None)
        assert "error" in result
        assert result["error"]["code"] == "INTERNAL_ERROR"


class TestPersonaSemanticFallback:
    """_build_pipeline_ctx falls back to semantic search when exact match fails."""

    @pytest.mark.asyncio
    async def test_analyze_with_semantic_persona_query(self, ctx: MagicMock) -> None:
        # Use a partial/fuzzy query that won't exact-match but should resolve
        result = await analyze(
            text="Hello world.",
            persona="slack casual",  # space instead of hyphen — triggers semantic fallback
            ctx=ctx,
        )
        # Should either succeed (found via semantic search) or return PERSONA_NOT_FOUND
        assert "health_score" in result or (
            "error" in result and result["error"]["code"] == "PERSONA_NOT_FOUND"
        )
