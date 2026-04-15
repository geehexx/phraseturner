"""Comparison output data models for phraseturner.

Implements §7.2 and §11.2 of the design specification.
Models for the ``compare`` tool response — per-dimension deltas,
sentence alignment, and concise comparison results.

Implements FR-TOOL-06.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from phraseturner.models.analysis import AnalysisMetadata


class DimensionDelta(BaseModel):
    """Per-dimension score delta between original and rewritten text.

    Implements FR-TOOL-06.

    Attributes:
        original: Dimension score for the original text.
        rewritten: Dimension score for the rewritten text.
        delta: Score change (rewritten - original). Positive means improvement.
    """

    original: float
    rewritten: float
    delta: float


class SentenceAlignment(BaseModel):
    """Mapping of an original sentence to its rewritten counterpart(s).

    Implements FR-TOOL-06.

    Attributes:
        original_index: Zero-based index of the original sentence.
        rewritten_indices: Indices of rewritten sentences aligned to this original.
        similarity: Cosine similarity between original and aligned rewritten text.
    """

    original_index: int
    rewritten_indices: list[int]
    similarity: float


class ComparisonResult(BaseModel):
    """Full comparison result returned by the ``compare`` tool.

    Implements FR-TOOL-06, FR-TOOL-08.

    Attributes:
        semantic_similarity: Overall cosine similarity between original and
            rewritten text (0.0-1.0 via bge-small-en-v1.5 FastEmbed).
        health_score_delta: Per-dimension score deltas keyed by dimension name.
        overall_improvement: Aggregate improvement score across all dimensions.
        sentence_alignment: Per-sentence alignment between original and rewrite.
        persona_compliance_delta: Persona compliance delta (when persona provided).
        next_steps: 1-3 contextual suggestions for the calling LLM.
        metadata: Analysis metadata including model versions and latency.
    """

    semantic_similarity: float = Field(ge=0.0, le=1.0)
    health_score_delta: dict[str, DimensionDelta]
    overall_improvement: float
    sentence_alignment: list[SentenceAlignment]
    persona_compliance_delta: DimensionDelta | None = None
    next_steps: list[str] = Field(
        default_factory=list, max_length=3
    )
    metadata: AnalysisMetadata


class ConciseComparisonResult(BaseModel):
    """Concise response for the ``compare`` tool.

    Omits per-dimension deltas and sentence alignment; returns only
    semantic similarity, overall improvement, and next steps.
    Implements FR-TOOL-09.

    Attributes:
        semantic_similarity: Overall cosine similarity (0.0-1.0).
        overall_improvement: Aggregate improvement score.
        next_steps: 1-3 contextual suggestions for the calling LLM.
        metadata: Analysis metadata including model versions and latency.
    """

    semantic_similarity: float = Field(ge=0.0, le=1.0)
    overall_improvement: float
    next_steps: list[str] = Field(
        default_factory=list, max_length=3
    )
    metadata: AnalysisMetadata


def rebuild_comparison_models() -> None:
    """Rebuild Pydantic models after forward references are resolved.

    Imports ``AnalysisMetadata`` at runtime and injects it into the
    module namespace so Pydantic can resolve the forward reference
    created by ``from __future__ import annotations``.
    """
    from phraseturner.models.analysis import AnalysisMetadata  # noqa: PLC0415

    # Inject into module globals so Pydantic can resolve the annotation
    globals()["AnalysisMetadata"] = AnalysisMetadata
    ComparisonResult.model_rebuild()
    ConciseComparisonResult.model_rebuild()
