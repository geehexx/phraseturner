"""phraseturner data models — analysis results, comparison, persona schemas, errors."""

from __future__ import annotations

from phraseturner.models.analysis import (
    AnalysisMetadata,
    AnalysisResult,
    ConciseAnalysisResult,
    DimensionScore,
    Flag,
    FlagsSummary,
    HealthScore,
    PersonaAlignment,
    ResponseFormat,
    SentenceAnalysis,
    Suggestion,
    T5SentenceAnalysis,
    ToneDelta,
)
from phraseturner.models.comparison import (
    ComparisonResult,
    ConciseComparisonResult,
    DimensionDelta,
    SentenceAlignment,
)
from phraseturner.models.errors import (
    AnalysisError,
    ToolError,
)
from phraseturner.models.inputs import (
    AnalyzeInput,
    FocusMode,
)
from phraseturner.models.persona import (
    PersonaCreateResult,
    PersonaDetail,
    PersonaSummary,
    ValidationError,
    ValidationResult,
)

__all__ = [
    "AnalysisError",
    "AnalysisMetadata",
    "AnalysisResult",
    "AnalyzeInput",
    "ComparisonResult",
    "ConciseAnalysisResult",
    "ConciseComparisonResult",
    "DimensionDelta",
    "DimensionScore",
    "Flag",
    "FlagsSummary",
    "FocusMode",
    "HealthScore",
    "PersonaAlignment",
    "PersonaCreateResult",
    "PersonaDetail",
    "PersonaSummary",
    "ResponseFormat",
    "SentenceAlignment",
    "SentenceAnalysis",
    "Suggestion",
    "T5SentenceAnalysis",
    "ToneDelta",
    "ToolError",
    "ValidationError",
    "ValidationResult",
]

# Resolve forward references for PersonaDetail (TYPE_CHECKING guard in persona.py).
from phraseturner.personas.schema import (  # noqa: F401
    BrandVoiceConfig,
    ChannelOverride,
    HealthScoreWeights,
    RuleConfig,
    ToneConfig,
    VocabularyConfig,
)

PersonaDetail.model_rebuild()
