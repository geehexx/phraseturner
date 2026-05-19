"""Pipeline orchestrator — 6-stage analysis with parallel execution.

Implements §4.1 of the design specification.

Stage 0 → (Stage 1 ‖ Stage 2) → Stage 3 → Stage 4 → Stage 5

Stage 1 runs 5 CPU-bound analyzers in parallel via ``asyncio.gather``
+ ``asyncio.to_thread``.  Stage 1 and Stage 2 run concurrently via
``asyncio.gather``.  Per-stage try/except ensures graceful degradation:
failed stages produce empty results and the pipeline continues with
``degraded=true``.

Quick score path: 0 → 1‖2 → 4 → 5 (skip Stage 3).
Full analysis path: 0 → 1‖2 → 3 → 4 → 5.

Requirements: FR-PIPELINE-01, FR-PIPELINE-02.
"""

from __future__ import annotations

import asyncio
import dataclasses
import time
from typing import TYPE_CHECKING, Any

import structlog

from phraseturner.models.analysis import (
    AnalysisMetadata,
    AnalysisResult,
    DimensionScore,
    HealthScore,
    PersonaAlignment,
    SentenceAnalysis,
    Suggestion,
    T5SentenceAnalysis,
)
from phraseturner.pipeline.additional import AdditionalSignalsResult, analyze_additional
from phraseturner.pipeline.ai_detection import AIDetectionResult, run_ai_detection
from phraseturner.pipeline.formatting import format_output
from phraseturner.pipeline.naturalness import NaturalnessResult, analyze_naturalness
from phraseturner.pipeline.readability import ReadabilityResult, analyze_readability
from phraseturner.pipeline.scoring import aggregate_scores, gaussian_readability_score
from phraseturner.pipeline.stage0 import run_stage0
from phraseturner.pipeline.tone import ToneResult, analyze_tone
from phraseturner.pipeline.tone_dimensions import compute_tone_dimensions
from phraseturner.pipeline.vocabulary import VocabularyResult, analyze_vocabulary
from phraseturner.t5 import (
    GatingContext,
    T5Runner,
    build_context,
    format_context_string,
    format_prompt,
    select_tasks,
    truncate_for_t5,
    validate_and_threshold,
)

if TYPE_CHECKING:
    from phraseturner.config import ServerConfig
    from phraseturner.personas.schema import PersonaConfig

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Tier thresholds (avoid magic numbers)
# ---------------------------------------------------------------------------
_TIER_SPACY: int = 1
_TIER_SLOP: int = 2
_TIER_T5: int = 3
_TIER_EMBED: int = 4


# ---------------------------------------------------------------------------
# PipelineContext — shared state for a single pipeline run
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class PipelineContext:
    """Shared context for a pipeline run. Implements §4.1.

    Attributes:
        nlp: Loaded spaCy ``Language`` model, or ``None`` (Tier 0).
        slop_detector: ``is-it-slop`` detector instance, or ``None``.
        t5_model: FLAN-T5 ONNX model handle, or ``None``.
        fastembed_model: FastEmbed model instance, or ``None``.
        config: Server configuration.
        persona: Resolved persona config, or ``None``.
    """

    nlp: Any
    slop_detector: Any
    t5_model: Any
    fastembed_model: Any
    config: ServerConfig
    persona: PersonaConfig | None = None


# ---------------------------------------------------------------------------
# Intermediate container for Stage 1+2 results
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class _StageResults:
    """Intermediate container holding unpacked Stage 1 and Stage 2 results."""

    readability: ReadabilityResult | None = None
    naturalness: NaturalnessResult | None = None
    vocabulary: VocabularyResult | None = None
    tone: ToneResult | None = None
    additional: AdditionalSignalsResult | None = None
    ai_detection: AIDetectionResult | None = None
    failed: list[str] = dataclasses.field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage 1 internal parallelism
# ---------------------------------------------------------------------------


async def _run_stage1(
    sentences: list[str],
    doc: Any,
) -> tuple[Any, ...]:
    """Run all 5 Stage 1 analyzers in parallel via thread pool.

    Each analyzer is CPU-bound and wrapped in ``asyncio.to_thread()``
    for true parallel execution.  ``return_exceptions=True`` ensures
    that a failure in one analyzer does not cancel the others.

    Implements AC-FR-PIPELINE-02.1.
    """
    return await asyncio.gather(
        asyncio.to_thread(analyze_readability, sentences, doc),
        asyncio.to_thread(analyze_naturalness, sentences, doc),
        asyncio.to_thread(analyze_vocabulary, sentences, doc),
        asyncio.to_thread(analyze_tone, sentences, doc),
        asyncio.to_thread(analyze_additional, sentences, doc),
        return_exceptions=True,
    )


# ---------------------------------------------------------------------------
# Helper: unpack Stage 1+2 gather results
# ---------------------------------------------------------------------------

_STAGE1_NAMES: tuple[str, ...] = (
    "stage1.readability",
    "stage1.naturalness",
    "stage1.vocabulary",
    "stage1.tone",
    "stage1.additional",
)
_STAGE1_FIELDS: tuple[str, ...] = (
    "readability",
    "naturalness",
    "vocabulary",
    "tone",
    "additional",
)


def _unpack_parallel_results(
    raw_stage1: Any,
    raw_stage2: Any,
) -> _StageResults:
    """Unpack Stage 1 and Stage 2 gather results into typed fields."""
    res = _StageResults()

    # Stage 1 — may be a tuple of results/exceptions, or itself an exception.
    if isinstance(raw_stage1, BaseException):
        logger.error("stage1_failed", error=str(raw_stage1))
        res.failed.append("stage1")
    elif raw_stage1 is not None:
        for idx, (name, field) in enumerate(
            zip(_STAGE1_NAMES, _STAGE1_FIELDS, strict=True),
        ):
            value = raw_stage1[idx]
            if isinstance(value, BaseException):
                logger.error(f"{field}_failed", error=str(value))
                res.failed.append(name)
            else:
                setattr(res, field, value)

    # Stage 2 — single result or exception.
    if isinstance(raw_stage2, BaseException):
        logger.error("stage2_failed", error=str(raw_stage2))
        res.failed.append("stage2")
    elif raw_stage2 is not None:
        res.ai_detection = raw_stage2

    return res


# ---------------------------------------------------------------------------
# Helper: compute dimension scores from raw analyzer results
# ---------------------------------------------------------------------------


def _score_naturalness(nat: NaturalnessResult) -> float:
    """Score naturalness from calibrated thresholds (0-100)."""
    burst_score = min(max((nat.burstiness - 0.20) / (0.35 - 0.20), 0.0), 1.0) * 40.0
    hapax_score = min(max((nat.hapax_ratio - 0.35) / (0.45 - 0.35), 0.0), 1.0) * 30.0
    zipf_score = min(max((0.96 - nat.zipf_r_squared) / (0.96 - 0.95), 0.0), 1.0) * 15.0
    diversity_part = min(nat.starter_diversity, 1.0) * 15.0
    return max(0.0, min(100.0, burst_score + hapax_score + zipf_score + diversity_part))


def _score_vocabulary(voc: VocabularyResult) -> float:
    """Score vocabulary from MTLD and TTR (0-100)."""
    mtld_part = min(voc.mtld / 100.0, 1.0) * 60.0
    ttr_part = min(voc.ttr, 1.0) * 40.0
    return max(0.0, min(100.0, mtld_part + ttr_part))


def _score_tone_compliance(tone: ToneResult) -> float:
    """Score tone compliance from sentiment balance and formality (0-100)."""
    compound = tone.overall_sentiment.compound
    sentiment_balance = max(0.0, 1.0 - abs(compound)) * 40.0
    formality_part = 30.0 + ((1.0 - tone.contraction_density) * 40.0)
    return max(0.0, min(100.0, sentiment_balance + formality_part))


def _compute_dimension_scores(
    results: _StageResults,
    persona_name: str | None = None,
) -> dict[str, float | None]:
    """Convert raw analyzer results into 0-100 dimension scores.

    Args:
        results: Unpacked Stage 1+2 results.
        persona_name: Optional persona/channel name for channel-specific
            readability targets.

    Returns:
        Dict mapping dimension names to scores (0-100) or ``None``.
    """
    from phraseturner.pipeline.scoring import (  # noqa: PLC0415
        _DEFAULT_SIGMA,
        _DEFAULT_TARGET_GRADE,
        CHANNEL_READABILITY_TARGETS,
    )

    scores: dict[str, float | None] = {
        "readability": None,
        "naturalness": None,
        "vocabulary": None,
        "semantic_preservation": None,
        "tone_compliance": None,
    }

    if results.readability is not None:
        target, sigma = _DEFAULT_TARGET_GRADE, _DEFAULT_SIGMA
        if persona_name and persona_name in CHANNEL_READABILITY_TARGETS:
            target, sigma = CHANNEL_READABILITY_TARGETS[persona_name]
        scores["readability"] = gaussian_readability_score(
            consensus_grade=results.readability.consensus_grade,
            target_grade=target,
            sigma=sigma,
        )

    if results.naturalness is not None:
        scores["naturalness"] = _score_naturalness(results.naturalness)

    if results.vocabulary is not None:
        scores["vocabulary"] = _score_vocabulary(results.vocabulary)

    if results.tone is not None:
        scores["tone_compliance"] = _score_tone_compliance(results.tone)

    return scores


# ---------------------------------------------------------------------------
# Helper: build per-sentence analysis objects
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class _SentenceBuilder:
    """Parameters for building per-sentence analysis objects."""

    sentences: list[str]
    results: _StageResults
    t5_results: list[T5SentenceAnalysis] = dataclasses.field(default_factory=list)


def _build_sentence_analyses(builder: _SentenceBuilder) -> list[SentenceAnalysis]:
    """Build per-sentence analysis objects from stage results."""
    analyses: list[SentenceAnalysis] = []
    r = builder.results
    for idx, text in enumerate(builder.sentences):
        readability_grade: float | None = None
        if r.readability is not None and idx < len(r.readability.per_sentence_grades):
            readability_grade = r.readability.per_sentence_grades[idx]

        vader_compound: float | None = None
        if r.tone is not None and idx < len(r.tone.per_sentence_sentiment):
            vader_compound = r.tone.per_sentence_sentiment[idx].compound

        info_density: float | None = None
        hedge_count = 0
        specificity: float | None = None
        coherence: float | None = None
        if r.additional is not None and idx < len(r.additional.per_sentence):
            sig = r.additional.per_sentence[idx]
            info_density = sig.information_density
            hedge_count = sig.hedge_count
            specificity = sig.specificity
            coherence = sig.coherence_to_next

        t5_analysis: T5SentenceAnalysis | None = None
        if idx < len(builder.t5_results):
            t5_analysis = builder.t5_results[idx]

        analyses.append(
            SentenceAnalysis(
                index=idx,
                text=text,
                readability_grade=readability_grade,
                word_count=len(text.split()),
                vader_compound=vader_compound,
                information_density=info_density,
                hedge_count=hedge_count,
                specificity=specificity,
                coherence_to_next=coherence,
                t5_analysis=t5_analysis,
            ),
        )
    return analyses


# ---------------------------------------------------------------------------
# Helper: build metadata
# ---------------------------------------------------------------------------


def _compute_tier(ctx: PipelineContext) -> int:
    """Determine operating tier from loaded models. FR-T5-06."""
    tier = 0
    if ctx.nlp is not None:
        tier = _TIER_SPACY
    if ctx.slop_detector is not None and tier >= _TIER_SPACY:
        tier = _TIER_SLOP
    if ctx.t5_model is not None and tier >= _TIER_SLOP:
        tier = _TIER_T5
    if ctx.fastembed_model is not None and tier >= _TIER_T5:
        tier = _TIER_EMBED
    return tier


def _build_metadata(
    start_time: float,
    token_count: int,
    ctx: PipelineContext,
    failed_stages: list[str],
    ai_detection: AIDetectionResult | None,
) -> AnalysisMetadata:
    """Build analysis metadata from pipeline run state."""
    latency_ms = (time.perf_counter() - start_time) * 1000.0

    model_versions: dict[str, str] = {}
    if ctx.nlp is not None:
        model_versions["spacy"] = ctx.nlp.meta.get("version", "unknown")
    if ctx.t5_model is not None:
        model_versions["t5"] = "flan-t5-base-int8"
    if ctx.fastembed_model is not None:
        model_versions["fastembed"] = "bge-small-en-v1.5"

    detection_method: str | None = None
    if ai_detection is not None:
        detection_method = ai_detection.detection_method

    return AnalysisMetadata(
        model_versions=model_versions,
        latency_ms=round(latency_ms, 1),
        token_count=token_count,
        operating_tier=_compute_tier(ctx),
        t5_available=ctx.t5_model is not None,
        degraded=len(failed_stages) > 0,
        failed_stages=failed_stages if failed_stages else None,
        ai_detection_method=detection_method,
    )


# ---------------------------------------------------------------------------
# Helper: run Stage 5 formatting
# ---------------------------------------------------------------------------


def _run_stage5(  # noqa: PLR0913
    sentence_analyses: list[SentenceAnalysis],
    results: _StageResults,
    persona: PersonaConfig | None,
    include_suggestions: bool,
    *,
    doc: Any = None,
    sentences: list[str] | None = None,
    text: str = "",
) -> tuple[list[Suggestion] | None, PersonaAlignment | None, list[str]]:
    """Execute Stage 5 output formatting. Returns suggestions, alignment, failed."""
    failed: list[str] = []
    suggestions: list[Suggestion] | None = None
    alignment: PersonaAlignment | None = None
    _stage5_doc = doc
    _stage5_sentences = sentences or [sa.text for sa in sentence_analyses]
    _stage5_text = text

    try:
        analysis_data: dict[str, Any] = {"sentences": []}
        for sa in sentence_analyses:
            analysis_data["sentences"].append(
                {
                    "text": sa.text,
                    "word_count": sa.word_count,
                    "readability_grade": sa.readability_grade,
                    "passive_voice": sa.passive_voice,
                    "vader_compound": sa.vader_compound,
                    "information_density": sa.information_density,
                    "hedge_count": sa.hedge_count,
                    "specificity": sa.specificity,
                    "coherence_to_next": sa.coherence_to_next,
                }
            )

        if results.tone is not None:
            analysis_data["tone_scores"] = compute_tone_dimensions(
                tone=results.tone,
                vocabulary=results.vocabulary,
                additional=results.additional,
                naturalness=results.naturalness,
                doc=_stage5_doc,
                sentences=_stage5_sentences,
                text=_stage5_text,
            )

        all_flags, raw_suggestions, alignment = format_output(
            analysis_data,
            persona=persona,
            text=_stage5_text,
            sentences=_stage5_sentences,
        )

        for idx, flags in enumerate(all_flags):
            if idx < len(sentence_analyses):
                sentence_analyses[idx].flags = flags

        if include_suggestions:
            suggestions = raw_suggestions
    except Exception:
        logger.exception("stage5_failed")
        failed.append("stage5")

    return suggestions, alignment, failed


# ---------------------------------------------------------------------------
# Helper: generate next_steps
# ---------------------------------------------------------------------------


def _generate_next_steps(
    health_score: HealthScore,
    persona: PersonaConfig | None,
    quick_score: bool,
) -> list[str]:
    """Generate 1-3 contextual next-step suggestions. Implements FR-TOOL-08."""
    steps: list[str] = []
    grade = health_score.letter_grade
    score = health_score.composite_score

    if quick_score:
        steps.append(
            f"Score is {grade} ({score:.0f}) — call `analyze` with "
            "`include_suggestions=true` for detailed improvement hints"
        )
    elif grade in ("D", "F"):
        steps.append(
            "Multiple dimensions need improvement — focus on the "
            "lowest-scoring dimension first, then re-run `score`"
        )
    elif grade == "C":
        steps.append(
            "Text is acceptable but could improve — review flagged "
            "sentences and call `score` after edits"
        )
    else:
        steps.append(
            f"Text scores well ({grade}) — consider running `compare` "
            "if you have an earlier draft to measure improvement"
        )

    if persona is not None:
        steps.append(
            f"Call `get_persona {persona.name}` to review full tone targets for this persona"
        )

    return steps[:3]


# ---------------------------------------------------------------------------
# Stage 3: FLAN-T5 deep analysis
# ---------------------------------------------------------------------------


def _populate_t5_analysis(  # noqa: PLR0912
    t5_analysis: T5SentenceAnalysis,
    task_outputs: dict[str, object],
) -> T5SentenceAnalysis:
    """Populate T5SentenceAnalysis fields from task output dict.

    Args:
        t5_analysis: Base T5SentenceAnalysis to update.
        task_outputs: Dict mapping task name to validated T5Output.

    Returns:
        Updated T5SentenceAnalysis with all available task results.
    """
    from phraseturner.t5.validation import (  # noqa: PLC0415
        T5Output,
        parse_persona_compliance_output,
        parse_tone_output,
    )

    updates: dict[str, object] = {}

    if "style_classification" in task_outputs:
        out = task_outputs["style_classification"]
        if isinstance(out, T5Output):
            updates["style_class"] = out.label
            updates["style_confidence"] = out.confidence

    if "ai_pattern_detection" in task_outputs:
        out = task_outputs["ai_pattern_detection"]
        if isinstance(out, T5Output):
            updates["ai_pattern"] = out.label
            updates["ai_pattern_confidence"] = out.confidence

    if "paraphrase_hints" in task_outputs:
        out = task_outputs["paraphrase_hints"]
        if isinstance(out, T5Output):
            updates["paraphrase_hint"] = out.label

    if "core_meaning" in task_outputs:
        out = task_outputs["core_meaning"]
        if isinstance(out, T5Output):
            updates["core_meaning"] = out.label

    if "sentence_function" in task_outputs:
        out = task_outputs["sentence_function"]
        if isinstance(out, T5Output):
            updates["sentence_function"] = out.label
            updates["sentence_function_confidence"] = out.confidence

    if "tone_assessment" in task_outputs:
        out = task_outputs["tone_assessment"]
        if isinstance(out, T5Output):
            tone_dims = parse_tone_output(out.label, out.confidence)
            updates["tone"] = {k: v.label for k, v in tone_dims.items()}

    if "persona_compliance" in task_outputs:
        out = task_outputs["persona_compliance"]
        if isinstance(out, T5Output):
            compliance_out, issue = parse_persona_compliance_output(out.label, out.confidence)
            updates["persona_compliance"] = compliance_out.label
            updates["persona_compliance_confidence"] = compliance_out.confidence
            updates["persona_issue"] = issue

    return t5_analysis.model_copy(update=updates) if updates else t5_analysis


def _resolve_t5_runner(ctx: PipelineContext) -> T5Runner | None:
    """Resolve a T5Runner from the pipeline context model handle.

    Args:
        ctx: Pipeline context with loaded models.

    Returns:
        A T5Runner instance, or None if the model is incompatible.
    """
    if isinstance(ctx.t5_model, T5Runner):
        return ctx.t5_model
    try:
        return T5Runner(session=ctx.t5_model[0], tokenizer=ctx.t5_model[1])
    except (TypeError, IndexError):
        logger.warning("t5_model_incompatible", model_type=type(ctx.t5_model).__name__)
        return None


async def _run_t5_for_sentence(  # noqa: PLR0913
    sent_idx: int,
    sentence: str,
    sentences: list[str],
    tasks: list[Any],
    runner: T5Runner,
    readability_grades: list[float] | None,
    vader_compounds: list[float] | None,
    ai_signal: str,
    persona: Any,
) -> T5SentenceAnalysis:
    """Run all T5 tasks for a single sentence.

    Args:
        sent_idx: Index of the sentence.
        sentence: The sentence text.
        sentences: All sentences (for context building).
        tasks: Selected T5 tasks to run.
        runner: T5Runner instance.
        readability_grades: Per-sentence readability grades.
        vader_compounds: Per-sentence VADER compounds.
        ai_signal: AI detection signal.
        persona: Optional persona config.

    Returns:
        Populated T5SentenceAnalysis for this sentence.
    """
    sent_ctx = build_context(
        sentence_idx=sent_idx,
        sentences=sentences,
        readability_grades=readability_grades,
        vader_compounds=vader_compounds,
        ai_signal=ai_signal,
        persona=persona,
    )
    context_str = format_context_string(sent_ctx)
    sentence_text, was_truncated = truncate_for_t5(sentence, context_str)

    task_outputs: dict[str, object] = {}
    for task in tasks:
        task_context: str | None = None
        if "{context}" in task.prompt_template:
            task_context = context_str

        prompt = format_prompt(task, sentence_text, context=task_context)
        try:
            raw_output, confidence = await runner.run_task(
                prompt=prompt,
                max_tokens=task.max_tokens,
                use_beam=task.use_beam_search,
            )
            validated = validate_and_threshold(raw_output, confidence, task)
            task_outputs[task.name] = validated
        except Exception:
            logger.warning("t5_task_failed", task=task.name, sentence_idx=sent_idx)

    t5_analysis = T5SentenceAnalysis(truncated=was_truncated)
    return _populate_t5_analysis(t5_analysis, task_outputs)


async def _run_stage3_t5(
    sentences: list[str],
    results: _StageResults,
    ctx: PipelineContext,
    include_suggestions: bool,
    sentence_analyses_ref: list[SentenceAnalysis] | None,
) -> list[T5SentenceAnalysis]:
    """Run FLAN-T5 deep analysis on each sentence. Implements FR-T5-02, FR-T5-03.

    Args:
        sentences: Sentence strings from Stage 0.
        results: Unpacked Stage 1+2 results.
        ctx: Pipeline context with loaded models.
        include_suggestions: Whether paraphrase hints are requested.
        sentence_analyses_ref: Optional list to populate with T5 results.

    Returns:
        List of T5SentenceAnalysis objects, one per sentence.
    """
    if ctx.t5_model is None:
        return []

    ai_signal = "uncertain"
    if results.ai_detection is not None:
        ai_signal = results.ai_detection.classification

    gating_ctx = GatingContext(
        ai_signal=ai_signal,
        include_suggestions=include_suggestions,
        has_persona=ctx.persona is not None,
    )
    tasks = select_tasks(gating_ctx)
    logger.debug(
        "stage3_t5_start",
        sentence_count=len(sentences),
        task_count=len(tasks),
        ai_signal=ai_signal,
    )

    vader_compounds: list[float] | None = None
    readability_grades: list[float] | None = None
    if results.tone is not None:
        vader_compounds = [s.compound for s in results.tone.per_sentence_sentiment]
    if results.readability is not None:
        readability_grades = results.readability.per_sentence_grades

    runner = _resolve_t5_runner(ctx)
    if runner is None:
        return []

    t5_results: list[T5SentenceAnalysis] = []
    for sent_idx, sentence in enumerate(sentences):
        result = await _run_t5_for_sentence(
            sent_idx,
            sentence,
            sentences,
            tasks,
            runner,
            readability_grades,
            vader_compounds,
            ai_signal,
            ctx.persona,
        )
        t5_results.append(result)

    logger.debug("stage3_t5_complete", sentence_count=len(t5_results))
    return t5_results


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


async def run_pipeline(  # noqa: PLR0913
    text: str,
    ctx: PipelineContext,
    *,
    quick_score: bool = False,
    include_suggestions: bool = False,
    original_text: str | None = None,
    focus: str = "full",
) -> AnalysisResult:
    """Run the 6-stage analysis pipeline. Implements §4.1.

    Orchestrates all pipeline stages with parallel execution where
    possible and per-stage error handling for graceful degradation.

    Quick score path: 0 → 1‖2 → 4 → 5 (skip Stage 3).
    Full analysis path: 0 → 1‖2 → 3 → 4 → 5.

    Implements FR-PIPELINE-01, FR-PIPELINE-02.

    Args:
        text: Input text to analyse.
        ctx: Pipeline context with loaded models and config.
        quick_score: If ``True``, skip Stage 3 (FLAN-T5).
        include_suggestions: If ``True``, include improvement hints.
        original_text: Original text for semantic preservation scoring.
        focus: Analysis focus mode (``full``, ``readability``, etc.).

    Returns:
        Complete ``AnalysisResult`` with health score, per-sentence
        analysis, and metadata.
    """
    start_time = time.perf_counter()
    failed_stages: list[str] = []

    # ── Stage 0: Input validation + sentence splitting ──────────────
    stage0 = await run_stage0(text, ctx.nlp, ctx.config)
    sentences = stage0.sentences
    logger.debug("stage0_complete", token_count=stage0.token_count, sentences=len(sentences))

    # ── Stage 1 + Stage 2: parallel execution ──────────────────────
    results = await _run_stages_1_2(sentences, stage0.doc, text, ctx)
    failed_stages.extend(results.failed)

    # ── Stage 3: FLAN-T5 deep analysis (skipped for quick_score) ───
    t5_results: list[T5SentenceAnalysis] = []
    if not quick_score and ctx.t5_model is not None:
        try:
            t5_results = await _run_stage3_t5(
                sentences=sentences,
                results=results,
                ctx=ctx,
                include_suggestions=include_suggestions,
                sentence_analyses_ref=None,
            )
        except Exception:
            logger.exception("stage3_failed")
            failed_stages.append("stage3")
            t5_results = []

    # ── Stage 4: Score aggregation ─────────────────────────────────
    health_score = _run_stage4(results, ctx, focus, original_text, failed_stages)

    # ── Stage 5: Output formatting ─────────────────────────────────
    sentence_analyses = _build_sentence_analyses(
        _SentenceBuilder(sentences=sentences, results=results, t5_results=t5_results),
    )
    suggestions, persona_alignment, s5_failed = _run_stage5(
        sentence_analyses,
        results,
        ctx.persona,
        include_suggestions,
        doc=stage0.doc,
        sentences=sentences,
        text=text,
    )
    failed_stages.extend(s5_failed)

    # ── Build metadata and return ──────────────────────────────────
    metadata = _build_metadata(
        start_time,
        stage0.token_count,
        ctx,
        failed_stages,
        results.ai_detection,
    )
    next_steps = _generate_next_steps(health_score, ctx.persona, quick_score)

    return AnalysisResult(
        health_score=health_score,
        sentences=sentence_analyses,
        persona_alignment=persona_alignment,
        suggestions=suggestions,
        next_steps=next_steps,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Stage 1+2 parallel runner
# ---------------------------------------------------------------------------


async def _run_stages_1_2(
    sentences: list[str],
    doc: Any,
    text: str,
    ctx: PipelineContext,
) -> _StageResults:
    """Run Stage 1 and Stage 2 concurrently. AC-FR-PIPELINE-02.2."""
    try:
        raw_stage1, raw_stage2 = await asyncio.gather(
            _run_stage1(sentences, doc),
            run_ai_detection(text, ctx.slop_detector, None),
            return_exceptions=True,
        )
    except Exception:
        logger.exception("stages_1_2_gather_failed")
        res = _StageResults()
        res.failed.extend(["stage1", "stage2"])
        return res

    return _unpack_parallel_results(raw_stage1, raw_stage2)


# ---------------------------------------------------------------------------
# Stage 4 runner
# ---------------------------------------------------------------------------


def _run_stage4(
    results: _StageResults,
    ctx: PipelineContext,
    focus: str,
    original_text: str | None,
    failed_stages: list[str],
) -> HealthScore:
    """Run Stage 4 score aggregation with fallback on failure."""
    try:
        persona_name = ctx.persona.name if ctx.persona is not None else None
        dimension_scores = _compute_dimension_scores(results, persona_name=persona_name)
        persona_weights = None
        if ctx.persona is not None:
            persona_weights = ctx.persona.health_score_weights

        return aggregate_scores(
            dimension_scores=dimension_scores,
            focus=focus,
            has_semantic=original_text is not None,
            persona_weights=persona_weights,
            persona_name=persona_name,
        )
    except Exception:
        logger.exception("stage4_failed")
        failed_stages.append("stage4")
        return HealthScore(
            composite_score=0.0,
            letter_grade="F",
            dimensions={
                "readability": DimensionScore(score=0.0, status="poor", weight=0.25),
                "naturalness": DimensionScore(score=0.0, status="poor", weight=0.30),
                "vocabulary": DimensionScore(score=0.0, status="poor", weight=0.20),
                "semantic_preservation": None,
                "tone_compliance": DimensionScore(score=0.0, status="poor", weight=0.10),
            },
        )
