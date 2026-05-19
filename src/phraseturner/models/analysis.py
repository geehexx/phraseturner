"""Analysis output data models for phraseturner.

Implements §7.1 and §11.2 of the design specification.
All models use Pydantic v2 with Field constraints for validation.

Implements FR-TOOL-01, FR-HEALTH-01, FR-HEALTH-02, FR-HEALTH-05, FR-HEALTH-06.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ResponseFormat(StrEnum):
    """Response verbosity modes. Implements FR-TOOL-09."""

    CONCISE = "concise"
    DETAILED = "detailed"


class DimensionScore(BaseModel):
    """Score for a single analysis dimension (readability, naturalness, etc.).

    Implements FR-HEALTH-01.

    Attributes:
        score: Dimension score from 0 to 100.
        status: Quality indicator — ``good``, ``warning``, or ``poor``.
        weight: Contribution weight to the composite score (0.0-1.0).
    """

    score: float = Field(ge=0.0, le=100.0)
    status: str  # good | warning | poor
    weight: float = Field(ge=0.0, le=1.0)


class HealthScore(BaseModel):
    """Composite health score across 5 analysis dimensions.

    Implements FR-HEALTH-01, FR-HEALTH-02.

    Attributes:
        composite_score: Weighted composite score from 0 to 100.
        letter_grade: Letter grade — A (≥85), B (≥70), C (≥55), D (≥40), F (<40).
        dimensions: Per-dimension scores keyed by dimension name.
            ``None`` values indicate dimensions that could not be computed.
    """

    composite_score: float = Field(ge=0.0, le=100.0)
    letter_grade: str  # A/B/C/D/F
    dimensions: dict[str, DimensionScore | None]


class Flag(BaseModel):
    """A quality flag raised during analysis.

    Implements FR-HEALTH-05.

    Attributes:
        code: Machine-readable flag code (e.g. ``PASSIVE_VOICE``).
        severity: Flag severity — ``error``, ``warning``, or ``suggestion``.
        message: Human-readable description of the issue.
    """

    code: str
    severity: str  # error | warning | suggestion
    message: str


class Suggestion(BaseModel):
    """An actionable improvement hint for a flagged sentence.

    Hints are directives only — NEVER rewritten text (CON-04).
    Implements FR-HEALTH-06.

    Attributes:
        sentence_index: Index of the sentence this suggestion targets.
        flag_code: The flag code that triggered this suggestion.
        hint: Directive describing what to improve (never a rewrite).
        impact: Estimated improvement impact from 0.0 to 1.0.
    """

    sentence_index: int
    flag_code: str
    hint: str
    impact: float = Field(ge=0.0, le=1.0)


class T5SentenceAnalysis(BaseModel):
    """FLAN-T5 deep analysis results for a single sentence.

    All fields are optional — populated only when T5 is available (Tier ≥ 3)
    and the corresponding task is gated in.

    Attributes:
        style_class: Detected style (formal/informal/neutral).
        style_confidence: Confidence score for style classification.
        ai_pattern: Detected AI writing pattern label.
        ai_pattern_confidence: Confidence score for AI pattern detection.
        paraphrase_hint: Directive hint for paraphrasing (when suggestions enabled).
        core_meaning: Extracted core meaning in ≤10 words.
        sentence_function: Sentence function label (claim/evidence/etc.).
        sentence_function_confidence: Confidence for sentence function.
        tone: Per-dimension tone assessment (low/medium/high).
        persona_compliance: Compliance label (compliant/minor-violation/major-violation).
        persona_compliance_confidence: Confidence for persona compliance.
        persona_issue: Description of the compliance issue, if any.
        truncated: Whether the sentence was truncated for the 512-token limit.
    """

    style_class: str | None = None
    style_confidence: float | None = None
    ai_pattern: str | None = None
    ai_pattern_confidence: float | None = None
    paraphrase_hint: str | None = None
    core_meaning: str | None = None
    sentence_function: str | None = None
    sentence_function_confidence: float | None = None
    tone: dict[str, str] | None = None
    persona_compliance: str | None = None
    persona_compliance_confidence: float | None = None
    persona_issue: str | None = None
    truncated: bool = False


class SentenceAnalysis(BaseModel):
    """Per-sentence analysis combining classical NLP and optional T5 results.

    Implements FR-TOOL-01.

    Attributes:
        index: Zero-based sentence index within the input text.
        text: The sentence text.
        flags: Quality flags raised for this sentence.
        t5_analysis: FLAN-T5 deep analysis (``None`` when T5 unavailable).
        readability_grade: Consensus readability grade for this sentence.
        word_count: Number of words in the sentence.
        passive_voice: Whether passive voice was detected.
        vader_compound: VADER compound sentiment score (-1.0 to 1.0).
        information_density: Ratio of content words to total words (0.0-1.0).
        hedge_count: Number of hedging expressions detected.
        specificity: Specificity score based on named entities and numbers.
        coherence_to_next: Lexical coherence to the following sentence.
    """

    index: int
    text: str
    flags: list[Flag] = Field(default_factory=list)
    t5_analysis: T5SentenceAnalysis | None = None
    readability_grade: float | None = None
    word_count: int = 0
    passive_voice: bool = False
    vader_compound: float | None = None
    information_density: float | None = None
    hedge_count: int = 0
    specificity: float | None = None
    coherence_to_next: float | None = None


class ToneDelta(BaseModel):
    """Delta between target and actual tone dimension values.

    Attributes:
        target: Target tone value from the persona (0.0-1.0).
        actual: Computed actual tone value (0.0-1.0).
        delta: Difference (actual - target).
    """

    target: float
    actual: float
    delta: float


class PersonaAlignment(BaseModel):
    """Persona compliance summary across tone dimensions and rules.

    Attributes:
        overall_compliance: Overall compliance score (0.0-1.0).
        tone_deltas: Per-dimension tone deltas keyed by dimension name.
        rule_violations: Number of persona rules violated.
        rule_passes: Number of persona rules passed.
    """

    overall_compliance: float = Field(ge=0.0, le=1.0)
    tone_deltas: dict[str, ToneDelta] = Field(default_factory=dict)
    rule_violations: int = 0
    rule_passes: int = 0


class AnalysisMetadata(BaseModel):
    """Metadata returned with every analysis response.

    Implements AC-FR-TOOL-01.6.

    Attributes:
        model_versions: Loaded model names and versions.
        latency_ms: Total analysis latency in milliseconds.
        token_count: Input text token count (spaCy tokenizer).
        operating_tier: Current operating tier (0-4).
        t5_available: Whether FLAN-T5 was available for this analysis.
        degraded: Whether the pipeline ran in degraded mode.
        failed_stages: List of stage names that failed (when degraded).
        ai_detection_method: Detection method used — ``ensemble`` or ``stylometric``.
    """

    model_versions: dict[str, str]
    latency_ms: float
    token_count: int
    operating_tier: int
    t5_available: bool
    degraded: bool = False
    failed_stages: list[str] | None = None
    ai_detection_method: str | None = None


class AnalysisResult(BaseModel):
    """Full analysis result returned by the ``analyze`` tool.

    Implements AC-FR-TOOL-01.1, FR-TOOL-08.

    Attributes:
        health_score: Composite health score with per-dimension breakdown.
        sentences: Per-sentence analysis results.
        persona_alignment: Persona compliance summary (when persona provided).
        suggestions: Ranked improvement hints (when ``include_suggestions=true``).
        next_steps: 1-3 contextual suggestions for the calling LLM.
        metadata: Analysis metadata including model versions and latency.
    """

    health_score: HealthScore
    sentences: list[SentenceAnalysis]
    persona_alignment: PersonaAlignment | None = None
    suggestions: list[Suggestion] | None = None
    next_steps: list[str] = Field(default_factory=list, max_length=3)
    metadata: AnalysisMetadata


# --- Concise response models (§11.2) ---


class FlagsSummary(BaseModel):
    """Compact flag summary for concise response mode.

    Implements FR-TOOL-09.

    Attributes:
        error_count: Number of error-severity flags.
        warning_count: Number of warning-severity flags.
        suggestion_count: Number of suggestion-severity flags.
        top_flags: Up to 5 most impactful flag codes.
    """

    error_count: int = 0
    warning_count: int = 0
    suggestion_count: int = 0
    top_flags: list[str] = Field(default_factory=list, max_length=5)


class ConciseAnalysisResult(BaseModel):
    """Concise response for the ``analyze`` tool.

    Omits per-sentence breakdowns; returns only health score,
    flags summary, and next steps. Implements FR-TOOL-09.

    Attributes:
        health_score: Composite health score with per-dimension breakdown.
        flags_summary: Aggregated flag counts and top flag codes.
        next_steps: 1-3 contextual suggestions for the calling LLM.
        metadata: Analysis metadata including model versions and latency.
    """

    health_score: HealthScore
    flags_summary: FlagsSummary
    next_steps: list[str] = Field(default_factory=list, max_length=3)
    metadata: AnalysisMetadata
