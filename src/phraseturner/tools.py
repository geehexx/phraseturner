"""MCP tool registrations for phraseturner.

Registers all 7 MCP tools on the ``mcp`` FastMCP instance with
annotations, 6-component docstrings, and ``next_steps`` in every
response via ``NextStepsBuilder``.

Error handling is centralised in ``error_handler.py``: the
``@tool_error_handler`` decorator wraps each tool function with
try/except for ``PhraseturnerError`` subclasses and unexpected
exceptions, returning structured ``ToolError`` responses.

Implements §2, §6, §11 of the design specification.
Requirements: FR-TOOL-01 through FR-TOOL-10, NFR-PERF-01 through NFR-PERF-04.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import numpy as np
import structlog
from fastmcp import Context  # noqa: TC002

from phraseturner.error_handler import tool_error_handler
from phraseturner.exceptions import PersonaNotFoundError, PhraseturnerError
from phraseturner.models.analysis import (
    AnalysisMetadata,
    ConciseAnalysisResult,
    FlagsSummary,
    ResponseFormat,
)
from phraseturner.models.comparison import (
    ComparisonResult,
    ConciseComparisonResult,
    DimensionDelta,
    SentenceAlignment,
    rebuild_comparison_models,
)
from phraseturner.models.persona import PersonaDetail, PersonaSummary
from phraseturner.next_steps import NextStepsBuilder
from phraseturner.personas.services import (
    create_persona as _create_persona_svc,
)
from phraseturner.personas.services import (
    validate_persona as _validate_persona_svc,
)
from phraseturner.pipeline.orchestrator import PipelineContext, run_pipeline
from phraseturner.server import mcp

# Resolve forward references in ComparisonResult (AnalysisMetadata)
rebuild_comparison_models()

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

_next_steps = NextStepsBuilder()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_dimension_deltas(
    result_orig: Any,
    result_rewr: Any,
) -> dict[str, DimensionDelta]:
    """Compute per-dimension score deltas between original and rewritten text."""
    delta_map: dict[str, DimensionDelta] = {}
    for dim_name in ("readability", "naturalness", "vocabulary", "tone_compliance"):
        orig_dim = result_orig.health_score.dimensions.get(dim_name)
        rewr_dim = result_rewr.health_score.dimensions.get(dim_name)
        orig_score = orig_dim.score if orig_dim is not None else 0.0
        rewr_score = rewr_dim.score if rewr_dim is not None else 0.0
        delta_map[dim_name] = DimensionDelta(
            original=orig_score,
            rewritten=rewr_score,
            delta=rewr_score - orig_score,
        )
    return delta_map


async def _compute_semantic_similarity(
    original: str,
    rewritten: str,
    models: Any,
) -> float:
    """Compute semantic similarity via FastEmbed (Tier 4)."""
    if not models.fastembed_available:
        return 0.0
    try:
        embeddings = await asyncio.to_thread(
            lambda: list(models.fastembed.embed([original, rewritten]))
        )
        vec_a = np.array(embeddings[0], dtype=np.float32)
        vec_b = np.array(embeddings[1], dtype=np.float32)
        norm_a = float(np.linalg.norm(vec_a))
        norm_b = float(np.linalg.norm(vec_b))
        if norm_a > 0.0 and norm_b > 0.0:
            sim = float(np.dot(vec_a, vec_b) / (norm_a * norm_b))
            return max(0.0, min(1.0, sim))
    except Exception:
        logger.warning("compare_embedding_failed", exc_info=True)
    return 0.0


def _build_sentence_alignment(
    result_orig: Any,
    result_rewr: Any,
    semantic_sim: float,
) -> list[SentenceAlignment]:
    """Build simple index-based sentence alignment."""
    orig_sents = [s.text for s in result_orig.sentences]
    rewr_sents = [s.text for s in result_rewr.sentences]
    alignment: list[SentenceAlignment] = []
    for idx in range(len(orig_sents)):
        rewr_idx = [idx] if idx < len(rewr_sents) else []
        alignment.append(SentenceAlignment(
            original_index=idx,
            rewritten_indices=rewr_idx,
            similarity=semantic_sim,
        ))
    return alignment


def _compute_persona_delta(
    result_orig: Any,
    result_rewr: Any,
) -> DimensionDelta | None:
    """Compute persona compliance delta between original and rewritten text."""
    orig_comp = (
        result_orig.persona_alignment.overall_compliance
        if result_orig.persona_alignment else 0.0
    )
    rewr_comp = (
        result_rewr.persona_alignment.overall_compliance
        if result_rewr.persona_alignment else 0.0
    )
    return DimensionDelta(
        original=orig_comp,
        rewritten=rewr_comp,
        delta=rewr_comp - orig_comp,
    )


def _build_comparison_metadata(
    start_time: float,
    result_orig: Any,
    result_rewr: Any,
) -> AnalysisMetadata:
    """Build metadata for a comparison result."""
    latency_ms = (time.perf_counter() - start_time) * 1000.0
    return AnalysisMetadata(
        model_versions=result_rewr.metadata.model_versions,
        latency_ms=round(latency_ms, 1),
        token_count=(
            result_orig.metadata.token_count
            + result_rewr.metadata.token_count
        ),
        operating_tier=result_rewr.metadata.operating_tier,
        t5_available=result_rewr.metadata.t5_available,
    )


def _get_lifespan_ctx(ctx: Context) -> dict[str, Any]:
    """Extract the lifespan context dict from a FastMCP Context.

    FastMCP 3.x stores the lifespan-yielded dict at
    ``ctx.request_context.lifespan_context``.

    Args:
        ctx: FastMCP tool context.

    Returns:
        The dict yielded by ``app_lifespan``.
    """
    return ctx.request_context.lifespan_context  # type: ignore[no-any-return,union-attr]


def _build_pipeline_ctx(
    lctx: dict[str, Any],
    persona_name: str | None = None,
) -> PipelineContext:
    """Build a ``PipelineContext`` from the lifespan context.

    Resolves the persona by name (exact match first, then semantic
    search) when ``persona_name`` is provided.

    Args:
        lctx: Lifespan context dict with ``config``, ``models``,
            ``persona_index`` keys.
        persona_name: Optional persona name or semantic query.

    Returns:
        Fully populated ``PipelineContext``.
    """
    config = lctx["config"]
    models = lctx["models"]
    persona_index = lctx["persona_index"]

    persona = None
    if persona_name is not None:
        # Try exact match first, then semantic search
        try:
            persona = persona_index.get(persona_name)
        except PhraseturnerError:
            results = persona_index.search(persona_name, limit=1)
            if results:
                persona = persona_index.get(results[0][0])
            else:
                raise PersonaNotFoundError(
                    f"No persona found matching '{persona_name}'",
                    details={"query": persona_name},
                ) from None

    return PipelineContext(
        nlp=models.nlp,
        slop_detector=models.slop_detector,
        t5_model=models.t5_session,
        fastembed_model=models.fastembed,
        config=config,
        persona=persona,
    )


# ===================================================================
# Tool 1: analyze — FR-TOOL-01, FR-TOOL-08, FR-TOOL-09
# ===================================================================


@mcp.tool(
    annotations={
        "title": "Analyse Text",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@tool_error_handler
async def analyze(  # noqa: PLR0913
    text: str,
    persona: str | None = None,
    focus: str = "full",
    include_suggestions: bool = False,
    original_text: str | None = None,
    response_format: str = "detailed",
    ctx: Context | None = None,
) -> dict[str, Any]:
    """PURPOSE: Analyse text quality against an optional persona, returning health scores,
    per-sentence flags, and improvement suggestions.

    CONSTRAINTS: Text must be 1-8000 tokens. Persona is optional (resolved from 4-tier
    directory). Target latency ≤500ms for ≤5 sentences.
    SIDE EFFECTS: None — read-only analysis.
    USAGE: Use for comprehensive text quality assessment. Use ``score`` instead for quick
    checks without per-sentence detail. Use ``compare`` when you have both original and
    rewritten text.
    FOLLOW-UP: If grade is D/F, rewrite flagged sentences and call ``score`` to verify. If
    persona compliance is low, call ``get_persona`` to review tone targets.
    ERRORS: TEXT_TOO_LONG (>8000 tokens) — split text. PERSONA_NOT_FOUND — call
    ``list_personas``. STAGE_FAILED — partial results returned with degraded=true.

    Implements FR-TOOL-01, FR-TOOL-08, FR-TOOL-09.

    Args:
        text: Text to analyse (1-8000 tokens).
        persona: Persona name or semantic query for resolution.
        focus: Analysis focus mode (full, readability, naturalness, persona_compliance).
        include_suggestions: Include up to 5 actionable hints.
        original_text: Original text for semantic preservation scoring.
        response_format: Response verbosity — ``concise`` or ``detailed``.
        ctx: FastMCP context (injected).

    Returns:
        Analysis result dict with health_score, sentences, next_steps, and metadata.
    """
    if ctx is None:
        raise RuntimeError("Server context not available")
    lctx = _get_lifespan_ctx(ctx)
    pipeline_ctx = _build_pipeline_ctx(lctx, persona)

    result = await run_pipeline(
        text,
        pipeline_ctx,
        quick_score=False,
        include_suggestions=include_suggestions,
        original_text=original_text,
        focus=focus,
    )

    # Override next_steps with NextStepsBuilder — FR-TOOL-08
    result.next_steps = _next_steps.for_analysis(result, persona)

    # FR-TOOL-09: concise mode
    fmt = ResponseFormat(response_format)
    if fmt == ResponseFormat.CONCISE:
        flags_summary = FlagsSummary(
            error_count=sum(
                1 for s in result.sentences for f in s.flags
                if f.severity == "error"
            ),
            warning_count=sum(
                1 for s in result.sentences for f in s.flags
                if f.severity == "warning"
            ),
            suggestion_count=sum(
                1 for s in result.sentences for f in s.flags
                if f.severity == "suggestion"
            ),
            top_flags=[
                f.code for s in result.sentences for f in s.flags
            ][:5],
        )
        concise = ConciseAnalysisResult(
            health_score=result.health_score,
            flags_summary=flags_summary,
            next_steps=result.next_steps,
            metadata=result.metadata,
        )
        return concise.model_dump()

    return result.model_dump()


# ===================================================================
# Tool 2: score — FR-TOOL-07, FR-TOOL-08
# ===================================================================


@mcp.tool(
    annotations={
        "title": "Quick Health Score",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
@tool_error_handler
async def score(
    text: str,
    persona: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """PURPOSE: Compute a quick health score without per-sentence T5 analysis.

    CONSTRAINTS: Text must be 1-8000 tokens. Skips FLAN-T5 (Stage 3). Target latency ≤50ms for
    ≤5 sentences.
    SIDE EFFECTS: None — read-only scoring.
    USAGE: Use for rapid quality checks during iterative rewriting. Use ``analyze`` when you
    need per-sentence detail and suggestions.
    FOLLOW-UP: If grade is D/F, call ``analyze`` with ``include_suggestions=true``. If grade is
    B/C, focus on the weakest dimension.
    ERRORS: TEXT_TOO_LONG (>8000 tokens) — split text. PERSONA_NOT_FOUND — call ``list_personas``.

    Implements FR-TOOL-07, FR-TOOL-08.

    Args:
        text: Text to score (1-8000 tokens).
        persona: Optional persona name for persona-weighted scoring.
        ctx: FastMCP context (injected).

    Returns:
        Health score dict with composite_score, letter_grade, dimensions,
        next_steps, and metadata.
    """
    if ctx is None:
        raise RuntimeError("Server context not available")
    lctx = _get_lifespan_ctx(ctx)
    pipeline_ctx = _build_pipeline_ctx(lctx, persona)

    result = await run_pipeline(
        text,
        pipeline_ctx,
        quick_score=True,
    )

    next_steps = _next_steps.for_score(result.health_score)

    return {
        **result.health_score.model_dump(),
        "metadata": result.metadata.model_dump(),
        "next_steps": next_steps,
    }


# ===================================================================
# Tool 3: compare — FR-TOOL-06, FR-TOOL-08, FR-TOOL-09
# ===================================================================


@mcp.tool(
    annotations={
        "title": "Compare Original vs Rewrite",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
@tool_error_handler
async def compare(
    original: str,
    rewritten: str,
    persona: str | None = None,
    response_format: str = "detailed",
    ctx: Context | None = None,
) -> dict[str, Any]:
    """PURPOSE: Compare an original text with a rewritten version, assessing quality
    improvement and meaning preservation.

    CONSTRAINTS: Both texts must be 1-8000 tokens. Target latency ≤800ms. Semantic similarity
    requires FastEmbed (Tier 4).
    SIDE EFFECTS: None — read-only comparison.
    USAGE: Use after rewriting text to measure improvement. Use ``analyze`` for single-text
    assessment. Use ``score`` for quick checks.
    FOLLOW-UP: If semantic_similarity < 0.7, rewrite more conservatively. If
    overall_improvement > 20, call ``score`` to confirm.
    ERRORS: TEXT_TOO_LONG (>8000 tokens) — split text. PERSONA_NOT_FOUND — call ``list_personas``.

    Implements FR-TOOL-06, FR-TOOL-08, FR-TOOL-09.

    Args:
        original: The original text before rewriting.
        rewritten: The rewritten text to compare against the original.
        persona: Optional persona name for persona compliance deltas.
        response_format: Response verbosity — ``concise`` or ``detailed``.
        ctx: FastMCP context (injected).

    Returns:
        Comparison result dict with semantic_similarity, health_score_delta,
        sentence_alignment, next_steps, and metadata.
    """
    if ctx is None:
        raise RuntimeError("Server context not available")
    lctx = _get_lifespan_ctx(ctx)
    start_time = time.perf_counter()

    # Run analysis on both texts in parallel — FR-TOOL-06
    pipeline_ctx_orig = _build_pipeline_ctx(lctx, persona)
    pipeline_ctx_rewr = _build_pipeline_ctx(lctx, persona)

    result_orig, result_rewr = await asyncio.gather(
        run_pipeline(original, pipeline_ctx_orig, quick_score=True),
        run_pipeline(rewritten, pipeline_ctx_rewr, quick_score=True),
    )

    delta_map = _compute_dimension_deltas(result_orig, result_rewr)
    overall_improvement = (
        result_rewr.health_score.composite_score
        - result_orig.health_score.composite_score
    )

    models = lctx["models"]
    semantic_sim = await _compute_semantic_similarity(original, rewritten, models)
    alignment = _build_sentence_alignment(result_orig, result_rewr, semantic_sim)

    persona_delta = _compute_persona_delta(result_orig, result_rewr) if persona else None
    metadata = _build_comparison_metadata(start_time, result_orig, result_rewr)

    comparison = ComparisonResult(
        semantic_similarity=semantic_sim,
        health_score_delta=delta_map,
        overall_improvement=overall_improvement,
        sentence_alignment=alignment,
        persona_compliance_delta=persona_delta,
        next_steps=[],
        metadata=metadata,
    )
    comparison.next_steps = _next_steps.for_comparison(comparison)

    # FR-TOOL-09: concise mode
    fmt = ResponseFormat(response_format)
    if fmt == ResponseFormat.CONCISE:
        concise = ConciseComparisonResult(
            semantic_similarity=comparison.semantic_similarity,
            overall_improvement=comparison.overall_improvement,
            next_steps=comparison.next_steps,
            metadata=metadata,
        )
        return concise.model_dump()

    return comparison.model_dump()


# ===================================================================
# Tool 4: list_personas — FR-TOOL-02, FR-TOOL-08
# ===================================================================


@mcp.tool(
    annotations={
        "title": "List Personas",
        "readOnlyHint": True,
        "idempotentHint": True,
    },
)
@tool_error_handler
async def list_personas(
    query: str | None = None,
    tags: list[str] | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """PURPOSE: List available personas with optional semantic search and tag filtering.

    CONSTRAINTS: No required parameters. Target latency ≤50ms.
    SIDE EFFECTS: None — read-only listing.
    USAGE: Use to discover available personas before calling ``analyze`` or ``get_persona``.
    Use ``query`` for semantic search, ``tags`` for filtering.
    FOLLOW-UP: Call ``get_persona <name>`` to view full details. Call ``analyze`` with a
    persona to analyse text.
    ERRORS: None expected — returns empty list if no personas match.

    Implements FR-TOOL-02, FR-TOOL-08.

    Args:
        query: Optional semantic search query for persona discovery.
        tags: Optional tag list to filter personas (all tags must match).
        ctx: FastMCP context (injected).

    Returns:
        Dict with ``personas`` list of PersonaSummary dicts and ``next_steps``.
    """
    if ctx is None:
        raise RuntimeError("Server context not available")
    lctx = _get_lifespan_ctx(ctx)
    persona_index = lctx["persona_index"]

    if query is not None:
        # Semantic or substring search — FR-TOOL-02.2
        search_results = persona_index.search(query)
        names = [name for name, _ in search_results]
    else:
        names = [p.name for p in persona_index.list_all()]

    summaries: list[dict[str, Any]] = []
    for name in names:
        try:
            config = persona_index.get(name)
        except PhraseturnerError:
            continue

        tier = persona_index.get_tier(name)

        # Tag filtering — FR-TOOL-02.3
        if tags is not None:
            config_tags = {t.lower() for t in config.tags}
            if not all(t.lower() in config_tags for t in tags):
                continue

        summary = PersonaSummary(
            name=config.name,
            description=config.description,
            tags=config.tags,
            channels=[c.value for c in config.channels],
            tier=tier,
            version=config.version,
        )
        summaries.append(summary.model_dump())

    return {
        "personas": summaries,
        "next_steps": _next_steps.for_list_personas(len(summaries)),
    }


# ===================================================================
# Tool 5: get_persona — FR-TOOL-03, FR-TOOL-08
# ===================================================================


@mcp.tool(
    annotations={
        "title": "Get Persona Detail",
        "readOnlyHint": True,
        "idempotentHint": True,
    },
)
@tool_error_handler
async def get_persona(
    name_or_query: str,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """PURPOSE: Retrieve the full definition of a persona by exact name or semantic query.

    CONSTRAINTS: Requires ``name_or_query`` parameter. Target latency ≤50ms.
    SIDE EFFECTS: None — read-only retrieval.
    USAGE: Use to inspect a persona's tone dimensions, rules, and vocabulary before using it
    with ``analyze``. Use ``list_personas`` first if unsure of the name.
    FOLLOW-UP: Call ``analyze`` with this persona to analyse text. Call ``validate_persona`` to
    check modifications.
    ERRORS: PERSONA_NOT_FOUND — call ``list_personas`` to see available names.

    Implements FR-TOOL-03, FR-TOOL-08.

    Args:
        name_or_query: Exact persona name or semantic search query.
        ctx: FastMCP context (injected).

    Returns:
        Dict with full persona detail and ``next_steps``.
    """
    if ctx is None:
        raise RuntimeError("Server context not available")
    lctx = _get_lifespan_ctx(ctx)
    persona_index = lctx["persona_index"]

    # Try exact match first, then semantic search — FR-TOOL-03.1, FR-TOOL-03.2
    config = None
    tier = "unknown"
    try:
        config = persona_index.get(name_or_query)
        tier = persona_index.get_tier(name_or_query)
    except PhraseturnerError:
        results = persona_index.search(name_or_query, limit=1)
        if results:
            config = persona_index.get(results[0][0])
            tier = persona_index.get_tier(results[0][0])

    if config is None:
        raise PersonaNotFoundError(
            f"No persona found matching '{name_or_query}'",
            details={"query": name_or_query},
        )

    detail = PersonaDetail(
        name=config.name,
        version=config.version,
        description=config.description,
        tone=config.tone.model_dump(),
        brand_voice=(
            config.brand_voice.model_dump()
            if config.brand_voice else None
        ),
        vocabulary=config.vocabulary.model_dump(),
        rules=[r.model_dump() for r in config.rules],
        channel_overrides={
            k.value: v.model_dump()
            for k, v in config.channel_overrides.items()
        },
        health_score_weights=(
            config.health_score_weights.model_dump()
            if config.health_score_weights else None
        ),
        tier=tier,
    )

    return {
        **detail.model_dump(),
        "next_steps": _next_steps.for_get_persona(config.name),
    }


# ===================================================================
# Tool 6: create_persona — FR-TOOL-04, FR-TOOL-08
# ===================================================================


@mcp.tool(
    annotations={
        "title": "Create Persona",
        "readOnlyHint": False,
        "destructiveHint": False,
    },
)
@tool_error_handler
async def create_persona(
    yaml_content: str,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """PURPOSE: Create a new persona from YAML content, validating and saving to the user
    directory.

    CONSTRAINTS: YAML must conform to the persona schema. Persona name must be unique in the
    user directory.
    SIDE EFFECTS: Writes a YAML file to the user persona directory. Registers the persona in
    the live index.
    USAGE: Use to define custom analysis rules. Call ``validate_persona`` first to check for
    errors without saving.
    FOLLOW-UP: Call ``analyze`` with the new persona name to test it. Call ``get_persona`` to
    verify the saved definition.
    ERRORS: PERSONA_VALIDATION_FAILED — fix YAML errors. PERSONA_EXISTS — use a different name.
    INVALID_YAML — check YAML syntax.

    Implements FR-TOOL-04, FR-TOOL-08.

    Args:
        yaml_content: Raw YAML string defining the persona.
        ctx: FastMCP context (injected).

    Returns:
        Dict with name, file_path, validation result, and ``next_steps``.
    """
    if ctx is None:
        raise RuntimeError("Server context not available")
    lctx = _get_lifespan_ctx(ctx)
    config = lctx["config"]
    persona_index = lctx["persona_index"]

    result = await _create_persona_svc(yaml_content, config, persona_index)

    return {
        **result.model_dump(),
        "next_steps": _next_steps.for_create_persona(result.name),
    }


# ===================================================================
# Tool 7: validate_persona — FR-TOOL-05, FR-TOOL-08
# ===================================================================


@mcp.tool(
    annotations={
        "title": "Validate Persona",
        "readOnlyHint": True,
        "idempotentHint": True,
    },
)
@tool_error_handler
async def validate_persona(
    yaml_content: str,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """PURPOSE: Validate persona YAML content without saving, checking schema conformance and
    rule correctness.

    CONSTRAINTS: Requires ``yaml_content`` parameter. Target latency ≤50ms.
    SIDE EFFECTS: None — pure validation with no file writes.
    USAGE: Use before ``create_persona`` to catch errors early. Use to iterate on persona
    definitions without saving intermediate versions.
    FOLLOW-UP: If valid, call ``create_persona`` to save. If invalid, fix errors and re-validate.
    ERRORS: None — validation errors are returned in the ``errors`` list, not as tool errors.

    Implements FR-TOOL-05, FR-TOOL-08.

    Args:
        yaml_content: Raw YAML string to validate.
        ctx: FastMCP context (injected).

    Returns:
        Dict with valid flag, errors list, warnings list, and ``next_steps``.
    """
    result = await _validate_persona_svc(yaml_content)

    return {
        **result.model_dump(),
        "next_steps": _next_steps.for_validate_persona(result.valid),
    }
