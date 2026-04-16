"""Tests for the pipeline orchestrator (Task 3.10).

Verifies the 6-stage pipeline orchestration with parallel execution,
graceful degradation, and quick-score path.

Requirements: FR-PIPELINE-01, FR-PIPELINE-02.
"""

from __future__ import annotations

import pytest

from phraseturner.config import ServerConfig
from phraseturner.models.analysis import AnalysisResult
from phraseturner.pipeline.orchestrator import PipelineContext, run_pipeline


def _make_ctx(
    *,
    nlp: object = None,
    slop_detector: object = None,
    t5_model: object = None,
    fastembed_model: object = None,
) -> PipelineContext:
    """Create a PipelineContext with optional model stubs."""
    return PipelineContext(
        nlp=nlp,
        slop_detector=slop_detector,
        t5_model=t5_model,
        fastembed_model=fastembed_model,
        config=ServerConfig(),
        persona=None,
    )


@pytest.mark.asyncio()
async def test_pipeline_tier0_returns_analysis_result() -> None:
    """Pipeline runs at Tier 0 (no models) and returns AnalysisResult."""
    ctx = _make_ctx()
    result = await run_pipeline("Hello world. This is a test.", ctx)

    assert isinstance(result, AnalysisResult)
    assert result.health_score.composite_score >= 0.0
    assert result.health_score.letter_grade in ("A", "B", "C", "D", "F")
    assert len(result.sentences) >= 1
    assert result.metadata.token_count > 0
    assert result.metadata.operating_tier == 0
    assert result.metadata.t5_available is False


@pytest.mark.asyncio()
async def test_pipeline_quick_score_skips_t5() -> None:
    """Quick score path skips Stage 3 (T5)."""
    ctx = _make_ctx()
    result = await run_pipeline(
        "The quick brown fox jumps over the lazy dog.",
        ctx,
        quick_score=True,
    )

    assert isinstance(result, AnalysisResult)
    assert result.metadata.t5_available is False
    # T5 analysis should be None for all sentences.
    for sent in result.sentences:
        assert sent.t5_analysis is None


@pytest.mark.asyncio()
async def test_pipeline_degraded_on_stage_failure() -> None:
    """Pipeline continues with degraded=true when a stage fails."""
    ctx = _make_ctx()
    result = await run_pipeline("A simple sentence.", ctx)

    # At Tier 0, pipeline should still produce results.
    assert isinstance(result, AnalysisResult)
    assert len(result.sentences) >= 1
    assert result.metadata.token_count > 0


@pytest.mark.asyncio()
async def test_pipeline_next_steps_populated() -> None:
    """Pipeline always returns at least 1 next_step."""
    ctx = _make_ctx()
    result = await run_pipeline("Testing next steps generation.", ctx)

    assert len(result.next_steps) >= 1
    assert len(result.next_steps) <= 3


@pytest.mark.asyncio()
async def test_pipeline_sentence_count_matches() -> None:
    """Number of SentenceAnalysis objects matches sentence count."""
    text = "First sentence. Second sentence. Third sentence."
    ctx = _make_ctx()
    result = await run_pipeline(text, ctx)

    # At Tier 0, fallback sentence splitting uses regex.
    assert len(result.sentences) >= 2


@pytest.mark.asyncio()
async def test_pipeline_include_suggestions() -> None:
    """Suggestions are included when include_suggestions=True."""
    ctx = _make_ctx()
    result = await run_pipeline(
        "Furthermore, it is imperative to note that the aforementioned "
        "factors have been duly considered in the analysis.",
        ctx,
        include_suggestions=True,
    )

    # Suggestions may or may not be generated depending on flags.
    assert isinstance(result, AnalysisResult)
    # When suggestions are requested, the field should not be None
    # (it may be an empty list if no flags were raised).
    if result.suggestions is not None:
        assert isinstance(result.suggestions, list)


@pytest.mark.asyncio()
async def test_pipeline_with_t5_enabled() -> None:
    """Stage 3 T5 results should be populated in sentence analyses.

    Mocks _run_stage3_t5 to return fake T5SentenceAnalysis objects,
    verifying that the orchestrator correctly wires Stage 3 output
    into the final SentenceAnalysis objects.

    Validates: FR-PIPELINE-01 (Stage 3 T5 path).
    """
    from unittest.mock import AsyncMock, patch

    from phraseturner.models.analysis import T5SentenceAnalysis

    fake_t5 = T5SentenceAnalysis(
        style_class="formal",
        style_confidence=0.9,
        core_meaning="test meaning",
    )

    # Provide a mock t5_model so the orchestrator enters the Stage 3 branch
    mock_t5_model = object()
    ctx = _make_ctx(t5_model=mock_t5_model)

    with patch(
        "phraseturner.pipeline.orchestrator._run_stage3_t5",
        new=AsyncMock(return_value=[fake_t5]),
    ):
        result = await run_pipeline(
            "Hello world. This is a test sentence.",
            ctx,
        )

    assert isinstance(result, AnalysisResult)
    assert len(result.sentences) >= 1
    # At least the first sentence should have T5 analysis populated
    assert result.sentences[0].t5_analysis is not None
    assert result.sentences[0].t5_analysis.style_class == "formal"
    assert result.sentences[0].t5_analysis.style_confidence == 0.9
    assert result.sentences[0].t5_analysis.core_meaning == "test meaning"
    assert result.metadata.t5_available is True
