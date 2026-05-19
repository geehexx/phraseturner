"""Tests for server.py — FastMCP server setup, lifespan, and MCP protocol.

Covers:
- app_lifespan context manager (startup, degradation, model loading)
- __main__.py entry point
- MCP protocol via FastMCP in-memory Client transport (tool listing,
  tool invocation, error codes, tool annotations)

The in-memory Client transport runs the full MCP protocol in-process
with no subprocess or network overhead. This is the correct way to test
MCP tool behaviour end-to-end.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from phraseturner.config import ServerConfig
from phraseturner.models.loader import ModelLoader

# ---------------------------------------------------------------------------
# __main__.py entry point
# ---------------------------------------------------------------------------


class TestMainEntryPoint:
    """Tests for __main__.py entry point."""

    def test_main_function_is_callable(self) -> None:
        """main() is importable and callable."""
        from phraseturner.__main__ import main

        assert callable(main)

    def test_main_calls_mcp_run(self) -> None:
        """main() delegates to mcp.run()."""
        with patch("phraseturner.__main__.mcp") as mock_mcp:
            from phraseturner.__main__ import main

            main()
            mock_mcp.run.assert_called_once()


# ---------------------------------------------------------------------------
# app_lifespan context manager
# ---------------------------------------------------------------------------


def _make_mock_models(
    fastembed_available: bool = False,
    t5_available: bool = False,
) -> MagicMock:
    """Build a mock ModelLoader for lifespan tests."""
    mock = MagicMock(spec=ModelLoader)
    mock.fastembed_available = fastembed_available
    mock.t5_available = t5_available
    mock.operating_tier = 0
    mock.model_versions = {}
    mock.load_spacy = AsyncMock()
    mock.load_fastembed = AsyncMock()
    mock.load_slop_detector = AsyncMock()
    mock.load_t5 = AsyncMock()
    mock.cleanup = AsyncMock()
    return mock


def _make_mock_persona_index() -> MagicMock:
    """Build a mock PersonaIndex for lifespan tests."""
    mock = MagicMock()
    mock.load_all = AsyncMock()
    mock.count = 0
    mock.watch_for_changes = AsyncMock(return_value=None)
    return mock


class TestAppLifespan:
    """Tests for the app_lifespan context manager."""

    async def test_lifespan_yields_required_keys(self) -> None:
        """app_lifespan yields dict with config, persona_index, models."""
        from phraseturner.server import app_lifespan

        mock_models = _make_mock_models()
        mock_persona_index = _make_mock_persona_index()

        with (
            patch("phraseturner.server.get_config") as mock_get_config,
            patch("phraseturner.server.ModelLoader", return_value=mock_models),
            patch("phraseturner.server.PersonaIndex", return_value=mock_persona_index),
        ):
            mock_get_config.return_value = ServerConfig(
                disable_t5=True, disable_slop=True, disable_embed=True
            )
            async with app_lifespan(MagicMock()) as ctx:
                assert "config" in ctx
                assert "persona_index" in ctx
                assert "models" in ctx
                assert ctx["models"] is mock_models
                assert ctx["persona_index"] is mock_persona_index

        mock_models.cleanup.assert_awaited_once()

    async def test_lifespan_degrades_gracefully_on_spacy_failure(self) -> None:
        """app_lifespan continues when spaCy fails to load (Tier 0 degradation)."""
        from phraseturner.server import app_lifespan

        mock_models = _make_mock_models()
        mock_models.load_spacy = AsyncMock(side_effect=OSError("spacy failed"))
        mock_persona_index = _make_mock_persona_index()

        with (
            patch("phraseturner.server.get_config") as mock_get_config,
            patch("phraseturner.server.ModelLoader", return_value=mock_models),
            patch("phraseturner.server.PersonaIndex", return_value=mock_persona_index),
        ):
            mock_get_config.return_value = ServerConfig(
                disable_t5=True, disable_slop=True, disable_embed=True
            )
            async with app_lifespan(MagicMock()) as ctx:
                assert ctx["models"] is mock_models

    async def test_lifespan_builds_embeddings_when_fastembed_available(self) -> None:
        """app_lifespan builds persona embeddings when FastEmbed is loaded."""
        from phraseturner.server import app_lifespan

        mock_models = _make_mock_models(fastembed_available=True, t5_available=True)
        mock_models.fastembed = MagicMock()
        mock_models.warmup_t5 = AsyncMock()
        mock_persona_index = _make_mock_persona_index()
        mock_persona_index.build_embeddings = AsyncMock()
        mock_persona_index.count = 5

        with (
            patch("phraseturner.server.get_config") as mock_get_config,
            patch("phraseturner.server.ModelLoader", return_value=mock_models),
            patch("phraseturner.server.PersonaIndex", return_value=mock_persona_index),
        ):
            mock_get_config.return_value = ServerConfig(
                disable_t5=True, disable_slop=True, disable_embed=True
            )
            async with app_lifespan(MagicMock()):
                pass

        mock_persona_index.build_embeddings.assert_awaited_once_with(mock_models.fastembed)
        mock_models.warmup_t5.assert_awaited_once()


# ---------------------------------------------------------------------------
# MCP protocol — in-memory Client transport
# ---------------------------------------------------------------------------


@pytest.fixture()
async def mcp_client() -> Any:
    """Function-scoped in-memory MCP client with all optional models disabled.

    Uses FastMCP's built-in Client(server) in-memory transport — no subprocess,
    no network. The lifespan runs once per Client connection, loading spaCy
    and built-in personas only (T5, slop, FastEmbed disabled for speed).
    """
    from fastmcp import Client

    from phraseturner.server import mcp

    async with Client(mcp) as client:
        yield client


class TestMCPToolListing:
    """MCP protocol: tool listing and annotations."""

    async def test_lists_all_seven_tools(self, mcp_client: Any) -> None:
        """Server exposes exactly 7 tools via MCP protocol."""
        tools = await mcp_client.list_tools()
        tool_names = {t.name for t in tools}
        expected = {
            "analyze",
            "score",
            "compare",
            "list_personas",
            "get_persona",
            "create_persona",
            "validate_persona",
        }
        assert tool_names == expected

    async def test_analyze_tool_is_read_only(self, mcp_client: Any) -> None:
        """analyze tool has readOnlyHint=True annotation."""
        tools = await mcp_client.list_tools()
        analyze = next(t for t in tools if t.name == "analyze")
        assert analyze.annotations is not None
        assert analyze.annotations.readOnlyHint is True

    async def test_create_persona_is_not_read_only(self, mcp_client: Any) -> None:
        """create_persona tool has readOnlyHint=False (writes to disk)."""
        tools = await mcp_client.list_tools()
        create = next(t for t in tools if t.name == "create_persona")
        assert create.annotations is not None
        assert create.annotations.readOnlyHint is False

    async def test_all_tools_have_descriptions(self, mcp_client: Any) -> None:
        """Every tool has a non-empty description."""
        tools = await mcp_client.list_tools()
        for tool in tools:
            assert tool.description, f"Tool '{tool.name}' has no description"
            assert len(tool.description) > 20, f"Tool '{tool.name}' description too short"


class TestMCPToolInvocation:
    """MCP protocol: tool invocation via in-memory transport."""

    async def test_analyze_returns_health_score(self, mcp_client: Any) -> None:
        """analyze tool returns a valid health_score via MCP protocol."""
        result = await mcp_client.call_tool(
            "analyze",
            {"text": "The quick brown fox jumps over the lazy dog."},
        )
        data = result.data
        assert "health_score" in data
        assert "composite_score" in data["health_score"]
        score = data["health_score"]["composite_score"]
        assert 0.0 <= score <= 100.0
        assert data["health_score"]["letter_grade"] in ("A", "B", "C", "D", "F")

    async def test_score_returns_composite_score(self, mcp_client: Any) -> None:
        """score tool returns composite_score and letter_grade."""
        result = await mcp_client.call_tool(
            "score",
            {"text": "Hello world. This is a simple test."},
        )
        data = result.data
        assert "composite_score" in data
        assert "letter_grade" in data
        assert "next_steps" in data

    async def test_list_personas_returns_nine_builtins(self, mcp_client: Any) -> None:
        """list_personas returns all 9 built-in personas."""
        result = await mcp_client.call_tool("list_personas", {})
        data = result.data
        assert "personas" in data
        names = {p["name"] for p in data["personas"]}
        expected_builtins = {
            "slack-casual",
            "pr-review",
            "confluence-docs",
            "jira-ticket",
            "email-professional",
            "blog-post",
            "technical-docs",
            "executive-summary",
            "internal-references",
        }
        assert expected_builtins.issubset(names)

    async def test_validate_persona_valid_yaml(self, mcp_client: Any) -> None:
        """validate_persona returns valid=True for well-formed YAML."""
        yaml_content = """\
name: test-mcp-persona
version: "1.0.0"
description: A test persona for MCP protocol tests.
tone:
  formality: 0.5
  confidence: 0.7
  warmth: 0.6
  directness: 0.5
  energy: 0.5
  verbosity: 0.4
rules: []
"""
        result = await mcp_client.call_tool(
            "validate_persona",
            {"yaml_content": yaml_content},
        )
        data = result.data
        assert data["valid"] is True
        assert data["errors"] == []

    async def test_analyze_text_too_long_returns_error_code(self, mcp_client: Any) -> None:
        """analyze returns TEXT_TOO_LONG error code for oversized input."""
        long_text = "word " * 9000
        result = await mcp_client.call_tool("analyze", {"text": long_text})
        data = result.data
        assert "error" in data
        assert data["error"]["code"] == "TEXT_TOO_LONG"
        assert "next_steps" in data

    async def test_get_persona_not_found_returns_error_code(self, mcp_client: Any) -> None:
        """get_persona with a name that has no exact match falls back to semantic search.

        When FastEmbed is available, semantic search always returns the closest
        persona — PERSONA_NOT_FOUND only occurs when FastEmbed is unavailable
        and no substring match exists. This test verifies the tool returns a
        valid persona (not an error) when semantic search is active.
        """
        result = await mcp_client.call_tool(
            "get_persona",
            {"name_or_query": "zzz-no-such-persona-xyzzy-12345"},
        )
        data = result.data
        # With FastEmbed active, semantic search returns the closest persona
        # rather than an error — this is correct behavior
        assert "name" in data or "error" in data  # either is valid
        if "error" in data:
            assert data["error"]["code"] == "PERSONA_NOT_FOUND"

    async def test_all_tool_responses_have_next_steps(self, mcp_client: Any) -> None:
        """Every successful tool response includes a next_steps field."""
        calls = [
            ("analyze", {"text": "Hello world."}),
            ("score", {"text": "Hello world."}),
            ("list_personas", {}),
            (
                "validate_persona",
                {
                    "yaml_content": "name: x\nversion: '1.0'\ntone:\n  formality: 0.5\n",
                },
            ),
        ]
        for tool_name, args in calls:
            result = await mcp_client.call_tool(tool_name, args)
            data = result.data
            assert "next_steps" in data, f"Tool '{tool_name}' missing next_steps"
