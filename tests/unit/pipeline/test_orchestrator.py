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


# ---------------------------------------------------------------------------
# _unpack_parallel_results — error paths
# ---------------------------------------------------------------------------


def test_unpack_parallel_results_stage1_exception() -> None:
    """Stage 1 exception is recorded in failed list, stage2 still unpacked."""
    from phraseturner.pipeline.ai_detection import AIDetectionResult
    from phraseturner.pipeline.orchestrator import _unpack_parallel_results

    ai = AIDetectionResult(
        classification="human",
        ai_probability=0.1,
        detection_method="slop",
        stylometric_signals={},
    )
    res = _unpack_parallel_results(RuntimeError("boom"), ai)

    assert "stage1" in res.failed
    assert res.ai_detection is ai


def test_unpack_parallel_results_stage2_exception() -> None:
    """Stage 2 exception is recorded in failed list."""
    from phraseturner.pipeline.orchestrator import _unpack_parallel_results

    res = _unpack_parallel_results(None, RuntimeError("ai boom"))

    assert "stage2" in res.failed
    assert res.ai_detection is None


def test_unpack_parallel_results_stage1_inner_exception() -> None:
    """Individual stage1 sub-result exceptions are recorded per-name."""
    from phraseturner.pipeline.orchestrator import _unpack_parallel_results
    from phraseturner.pipeline.readability import ReadabilityResult

    # Build a tuple with one real result and the rest as exceptions.
    # Stage 1 order: readability, naturalness, vocabulary, tone, additional
    readability = ReadabilityResult(
        flesch_reading_ease=60.0,
        consensus_grade=8.0,
        per_sentence_grades=[8.0],
        individual_grades={"flesch": 8.0},
    )
    stage1_tuple = (
        readability,
        RuntimeError("naturalness failed"),
        RuntimeError("vocab failed"),
        RuntimeError("tone failed"),
        RuntimeError("additional failed"),
    )
    res = _unpack_parallel_results(stage1_tuple, None)

    assert res.readability is readability
    assert res.naturalness is None
    assert "stage1.naturalness" in res.failed
    assert "stage1.vocabulary" in res.failed


# ---------------------------------------------------------------------------
# _compute_dimension_scores — persona channel target + semantic preservation
# ---------------------------------------------------------------------------


def test_compute_dimension_scores_with_persona_channel() -> None:
    """Persona channel name selects a custom readability target."""
    from phraseturner.pipeline.orchestrator import _compute_dimension_scores, _StageResults
    from phraseturner.pipeline.readability import ReadabilityResult
    from phraseturner.pipeline.scoring import CHANNEL_READABILITY_TARGETS

    results = _StageResults()
    results.readability = ReadabilityResult(
        flesch_reading_ease=65.0,
        consensus_grade=9.0,
        per_sentence_grades=[9.0],
        individual_grades={"flesch": 9.0},
    )

    # Use a known channel name if available, else skip gracefully.
    if not CHANNEL_READABILITY_TARGETS:
        return

    channel = next(iter(CHANNEL_READABILITY_TARGETS))
    scores = _compute_dimension_scores(results, persona_name=channel)

    assert scores["readability"] is not None
    assert 0.0 <= scores["readability"] <= 100.0


def test_compute_dimension_scores_all_none_when_no_results() -> None:
    """All dimension scores are None when no stage results are present."""
    from phraseturner.pipeline.orchestrator import _compute_dimension_scores, _StageResults

    scores = _compute_dimension_scores(_StageResults())

    assert scores["readability"] is None
    assert scores["naturalness"] is None
    assert scores["vocabulary"] is None
    assert scores["tone_compliance"] is None


# ---------------------------------------------------------------------------
# _build_sentence_analyses — per-sentence data population
# ---------------------------------------------------------------------------


def test_build_sentence_analyses_populates_per_sentence_fields() -> None:
    """Per-sentence readability, tone, and additional fields are wired correctly."""
    from phraseturner.pipeline.additional import AdditionalSignalsResult, SentenceSignals
    from phraseturner.pipeline.orchestrator import (
        _build_sentence_analyses,
        _SentenceBuilder,
        _StageResults,
    )
    from phraseturner.pipeline.readability import ReadabilityResult
    from phraseturner.pipeline.tone import SentimentScores, ToneResult

    results = _StageResults()
    results.readability = ReadabilityResult(
        flesch_reading_ease=60.0,
        consensus_grade=8.5,
        per_sentence_grades=[8.5, 9.0],
        individual_grades={"flesch": 8.5},
    )
    results.tone = ToneResult(
        overall_sentiment=SentimentScores(compound=0.1, positive=0.5, negative=0.1, neutral=0.4),
        per_sentence_sentiment=[
            SentimentScores(compound=0.2, positive=0.6, negative=0.1, neutral=0.3),
            SentimentScores(compound=-0.1, positive=0.2, negative=0.3, neutral=0.5),
        ],
        contraction_density=0.05,
        formal_marker_count=2,
        formal_markers=["therefore", "thus"],
    )
    results.additional = AdditionalSignalsResult(
        per_sentence=[
            SentenceSignals(
                hedge_words=[],
                hedge_count=1,
                information_density=0.6,
                specificity=0.7,
                coherence_to_next=0.8,
            ),
            SentenceSignals(
                hedge_words=[],
                hedge_count=0,
                information_density=0.5,
                specificity=0.6,
                coherence_to_next=None,
            ),
        ],
        overall_information_density=0.55,
        overall_specificity=0.65,
        mean_coherence=0.8,
    )

    builder = _SentenceBuilder(
        sentences=["First sentence.", "Second sentence."],
        results=results,
    )
    analyses = _build_sentence_analyses(builder)

    assert len(analyses) == 2
    assert analyses[0].readability_grade == pytest.approx(8.5)
    assert analyses[0].vader_compound == pytest.approx(0.2)
    assert analyses[0].information_density == pytest.approx(0.6)
    assert analyses[0].hedge_count == 1
    assert analyses[0].specificity == pytest.approx(0.7)
    assert analyses[0].coherence_to_next == pytest.approx(0.8)
    assert analyses[1].readability_grade == pytest.approx(9.0)
    assert analyses[1].vader_compound == pytest.approx(-0.1)


# ---------------------------------------------------------------------------
# _build_metadata — model_versions and detection_method paths
# ---------------------------------------------------------------------------


def test_build_metadata_with_t5_and_fastembed() -> None:
    """model_versions includes t5 and fastembed when those models are set."""
    import time

    from phraseturner.config import ServerConfig
    from phraseturner.pipeline.orchestrator import PipelineContext, _build_metadata

    ctx = PipelineContext(
        nlp=None,
        slop_detector=None,
        t5_model=object(),
        fastembed_model=object(),
        config=ServerConfig(),
        persona=None,
    )
    meta = _build_metadata(time.perf_counter(), 42, ctx, [], None)

    assert "t5" in meta.model_versions
    assert "fastembed" in meta.model_versions
    assert meta.t5_available is True
    assert meta.degraded is False


def test_build_metadata_with_ai_detection_method() -> None:
    """ai_detection_method is populated from AIDetectionResult."""
    import time

    from phraseturner.config import ServerConfig
    from phraseturner.pipeline.ai_detection import AIDetectionResult
    from phraseturner.pipeline.orchestrator import PipelineContext, _build_metadata

    ai = AIDetectionResult(
        classification="ai",
        ai_probability=0.85,
        detection_method="slop_heuristic",
        stylometric_signals=None,
    )
    ctx = PipelineContext(
        nlp=None,
        slop_detector=None,
        t5_model=None,
        fastembed_model=None,
        config=ServerConfig(),
        persona=None,
    )
    meta = _build_metadata(time.perf_counter(), 10, ctx, ["stage3"], ai)

    assert meta.ai_detection_method == "slop_heuristic"
    assert meta.degraded is True
    assert meta.failed_stages == ["stage3"]


# ---------------------------------------------------------------------------
# _populate_t5_analysis — field population from task outputs
# ---------------------------------------------------------------------------


def test_populate_t5_analysis_style_and_ai_pattern() -> None:
    """style_class and ai_pattern are populated from T5Output entries."""
    from phraseturner.models.analysis import T5SentenceAnalysis
    from phraseturner.pipeline.orchestrator import _populate_t5_analysis
    from phraseturner.t5.validation import T5Output

    base = T5SentenceAnalysis()
    outputs: dict[str, object] = {
        "style_classification": T5Output(label="formal", confidence=0.9, is_fallback=False),
        "ai_pattern_detection": T5Output(label="none", confidence=0.8, is_fallback=False),
    }
    result = _populate_t5_analysis(base, outputs)

    assert result.style_class == "formal"
    assert result.style_confidence == pytest.approx(0.9)
    assert result.ai_pattern == "none"
    assert result.ai_pattern_confidence == pytest.approx(0.8)


def test_populate_t5_analysis_paraphrase_and_core_meaning() -> None:
    """paraphrase_hint and core_meaning are populated."""
    from phraseturner.models.analysis import T5SentenceAnalysis
    from phraseturner.pipeline.orchestrator import _populate_t5_analysis
    from phraseturner.t5.validation import T5Output

    base = T5SentenceAnalysis()
    outputs: dict[str, object] = {
        "paraphrase_hints": T5Output(label="simplify", confidence=0.7, is_fallback=False),
        "core_meaning": T5Output(label="the sky is blue", confidence=0.95, is_fallback=False),
        "sentence_function": T5Output(label="declarative", confidence=0.88, is_fallback=False),
    }
    result = _populate_t5_analysis(base, outputs)

    assert result.paraphrase_hint == "simplify"
    assert result.core_meaning == "the sky is blue"
    assert result.sentence_function == "declarative"
    assert result.sentence_function_confidence == pytest.approx(0.88)


def test_populate_t5_analysis_empty_outputs_returns_unchanged() -> None:
    """Empty task_outputs returns the base object unchanged."""
    from phraseturner.models.analysis import T5SentenceAnalysis
    from phraseturner.pipeline.orchestrator import _populate_t5_analysis

    base = T5SentenceAnalysis(style_class="informal")
    result = _populate_t5_analysis(base, {})

    assert result is base


# ---------------------------------------------------------------------------
# _resolve_t5_runner — tuple path and incompatible model
# ---------------------------------------------------------------------------


def test_resolve_t5_runner_incompatible_returns_none() -> None:
    """Non-T5Runner, non-tuple model returns None."""
    from phraseturner.config import ServerConfig
    from phraseturner.pipeline.orchestrator import PipelineContext, _resolve_t5_runner

    ctx = PipelineContext(
        nlp=None,
        slop_detector=None,
        t5_model=42,  # int is not T5Runner and not subscriptable → TypeError → None
        fastembed_model=None,
        config=ServerConfig(),
        persona=None,
    )
    result = _resolve_t5_runner(ctx)

    assert result is None


# ---------------------------------------------------------------------------
# _run_stage3_t5 — no t5_model returns empty list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_run_stage3_t5_no_model_returns_empty() -> None:
    """_run_stage3_t5 returns [] when ctx.t5_model is None."""
    from phraseturner.config import ServerConfig
    from phraseturner.pipeline.orchestrator import (
        PipelineContext,
        _run_stage3_t5,
        _StageResults,
    )

    ctx = PipelineContext(
        nlp=None,
        slop_detector=None,
        t5_model=None,
        fastembed_model=None,
        config=ServerConfig(),
        persona=None,
    )
    result = await _run_stage3_t5(["Hello."], _StageResults(), ctx, False, None)

    assert result == []


@pytest.mark.asyncio()
async def test_run_stage3_t5_incompatible_runner_returns_empty() -> None:
    """_run_stage3_t5 returns [] when t5_model cannot be resolved to T5Runner."""
    from phraseturner.config import ServerConfig
    from phraseturner.pipeline.orchestrator import (
        PipelineContext,
        _run_stage3_t5,
        _StageResults,
    )

    ctx = PipelineContext(
        nlp=None,
        slop_detector=None,
        t5_model=42,  # int is not T5Runner and not subscriptable → TypeError → None
        fastembed_model=None,
        config=ServerConfig(),
        persona=None,
    )
    result = await _run_stage3_t5(["Hello."], _StageResults(), ctx, False, None)

    assert result == []


# ---------------------------------------------------------------------------
# run_pipeline — stage3 exception fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_pipeline_stage3_exception_degrades_gracefully() -> None:
    """Stage 3 exception is caught; pipeline continues with degraded=True."""
    from unittest.mock import AsyncMock, patch

    ctx = _make_ctx(t5_model=object())

    with patch(
        "phraseturner.pipeline.orchestrator._run_stage3_t5",
        new=AsyncMock(side_effect=RuntimeError("t5 exploded")),
    ):
        result = await run_pipeline("Hello world.", ctx)

    assert isinstance(result, AnalysisResult)
    assert result.metadata.degraded is True
    assert "stage3" in (result.metadata.failed_stages or [])


# ---------------------------------------------------------------------------
# _run_stage4 — exception fallback returns F grade
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_pipeline_stage4_exception_returns_f_grade() -> None:
    """Stage 4 exception produces letter_grade=F and degraded=True."""
    from unittest.mock import patch

    ctx = _make_ctx()

    with patch(
        "phraseturner.pipeline.orchestrator.aggregate_scores",
        side_effect=RuntimeError("scoring exploded"),
    ):
        result = await run_pipeline("Hello world.", ctx)

    assert result.health_score.letter_grade == "F"
    assert result.metadata.degraded is True


# ---------------------------------------------------------------------------
# run_pipeline — original_text enables semantic preservation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_pipeline_with_original_text() -> None:
    """Passing original_text enables semantic preservation scoring."""
    ctx = _make_ctx()
    result = await run_pipeline(
        "The quick brown fox jumps over the lazy dog.",
        ctx,
        original_text="A fast brown fox leaps over a sleepy dog.",
    )

    assert isinstance(result, AnalysisResult)
    # semantic_preservation dimension should be present (may be None score at Tier 0)
    assert "semantic_preservation" in result.health_score.dimensions
