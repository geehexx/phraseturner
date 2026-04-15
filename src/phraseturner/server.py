"""FastMCP server setup with lifespan context manager.

Loads all models and personas at startup via the ``app_lifespan`` async
context manager and shares them across tool calls via
``ctx.lifespan_context``.

Implements §1.1, §1.3.
Requirements: FR-T5-01, FR-T5-06, NFR-PERF-06, NFR-DIST-02.
"""

from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import structlog
from fastmcp import FastMCP

from phraseturner.config import ServerConfig, get_config
from phraseturner.models.loader import ModelLoader
from phraseturner.personas.index import PersonaIndex

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger: structlog.stdlib.BoundLogger = structlog.get_logger()


class _LifespanContext:
    """Typed wrapper for the lifespan context dict.

    Provides attribute access to the three objects shared across all
    MCP tool calls.  Stored in ``ctx.lifespan_context`` by FastMCP.
    """

    __slots__ = ("config", "models", "persona_index")

    def __init__(
        self,
        config: ServerConfig,
        persona_index: PersonaIndex,
        models: ModelLoader,
    ) -> None:
        self.config = config
        self.persona_index = persona_index
        self.models = models


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    """Load models and personas at startup. Implements FR-T5-01.

    Startup sequence (§1.3):
        1. Load ``ServerConfig`` via pydantic-settings.
        2. Load spaCy model (Tier 1+; Tier 0 fallback on failure).
        3. Load personas from all 4 directory tiers.
        4. Load optional models in parallel (FastEmbed, is-it-slop, T5).
        5. Build persona embedding index (requires FastEmbed).
        6. Warm up T5 with dummy inference.
        7. Start filesystem watcher for hot-reload.

    Yields:
        Dict with ``config``, ``persona_index``, and ``models`` keys
        accessible via ``ctx.lifespan_context`` in tool handlers.

    Args:
        server: The FastMCP server instance (injected by FastMCP).
    """
    config = get_config()
    models = ModelLoader(config)
    persona_index = PersonaIndex(config)

    # Step 1: Load spaCy (required for Tier 1+; Tier 0 fallback)
    try:
        await models.load_spacy()
    except Exception:
        logger.warning(
            "spacy_load_failed",
            msg="spaCy failed to load — degrading to Tier 0 (textstat-only)",
        )

    # Step 2: Load personas from all 4 tiers
    await persona_index.load_all()

    # Step 3: Load optional models in parallel — NFR-PERF-06
    await asyncio.gather(
        models.load_fastembed(),
        models.load_slop_detector(),
        models.load_t5(),
        return_exceptions=True,
    )

    # Step 4: Build persona embedding index (requires FastEmbed)
    if models.fastembed_available:
        await persona_index.build_embeddings(models.fastembed)

    # Step 5: Warm up T5 model
    if models.t5_available:
        await models.warmup_t5()

    # Step 6: Start filesystem watcher for hot-reload
    watcher_task = asyncio.create_task(
        persona_index.watch_for_changes(models.fastembed)
    )

    # Log startup status — FR-T5-06
    logger.info(
        "server_started",
        operating_tier=models.operating_tier,
        personas_loaded=persona_index.count,
        model_versions=models.model_versions,
    )

    # Pre-import pipeline modules to avoid first-call latency spike
    # (lexicalrichness takes ~2s to import, scipy.stats ~1.6s)
    import phraseturner.pipeline.orchestrator  # noqa: F401, PLC0415

    try:
        yield {
            "config": config,
            "persona_index": persona_index,
            "models": models,
        }
    finally:
        watcher_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await watcher_task
        await models.cleanup()
        logger.info("server_shutdown")


mcp = FastMCP(
    "phraseturner",
    instructions="Text analysis MCP server with configurable personas",
    lifespan=app_lifespan,
)

# Register all MCP tools on the mcp instance.
# This import MUST come after mcp is created above.
import phraseturner.tools as _tools  # noqa: F401, E402
