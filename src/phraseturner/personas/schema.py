"""Persona configuration schema for phraseturner.

Implements §3.2 of the design specification.
All persona YAML files are validated against these Pydantic models.

Implements FR-PERSONA-03, FR-PERSONA-08, FR-HEALTH-03.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

_WEIGHTS_SUM_TOLERANCE = 0.001

class ToneConfig(BaseModel):
    """6 tone dimensions, each 0.0-1.0.

    Implements AC-FR-PERSONA-03.2.

    Attributes:
        formality: Formal (1.0) vs casual (0.0) register.
        confidence: Assertive (1.0) vs tentative (0.0) voice.
        warmth: Warm/friendly (1.0) vs neutral/distant (0.0) tone.
        directness: Direct (1.0) vs indirect (0.0) communication.
        energy: High-energy (1.0) vs calm (0.0) delivery.
        verbosity: Verbose (1.0) vs concise (0.0) expression.
    """

    formality: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    warmth: float = Field(default=0.5, ge=0.0, le=1.0)
    directness: float = Field(default=0.5, ge=0.0, le=1.0)
    energy: float = Field(default=0.5, ge=0.0, le=1.0)
    verbosity: float = Field(default=0.5, ge=0.0, le=1.0)


class BrandVoiceConfig(BaseModel):
    """Brand voice configuration for persona identity.

    Implements AC-FR-PERSONA-03.3.

    Attributes:
        persona_card: Free-text description of the persona's character.
        personality_traits: List of personality trait keywords.
        catchphrases: Signature phrases the persona uses.
        forbidden_phrases: Phrases the persona must never use.
        prompt_scaffold: Template scaffold for LLM prompt construction.
    """

    persona_card: str | None = None
    personality_traits: list[str] = Field(default_factory=list)
    catchphrases: list[str] = Field(default_factory=list)
    forbidden_phrases: list[str] = Field(default_factory=list)
    prompt_scaffold: str | None = None


class VocabularyConfig(BaseModel):
    """Approved and prohibited vocabulary lists.

    Implements AC-FR-PERSONA-03.4.

    Attributes:
        approved: Words and phrases that are encouraged.
        prohibited: Words and phrases that should be flagged.
    """

    approved: list[str] = Field(default_factory=list)
    prohibited: list[str] = Field(default_factory=list)


class RuleType(StrEnum):
    """13 rule types: 10 Vale-compatible + 3 phraseturner extensions.

    Implements AC-FR-PERSONA-02.1, AC-FR-PERSONA-08.1.
    """

    EXISTENCE = "existence"
    SUBSTITUTION = "substitution"
    OCCURRENCE = "occurrence"
    REPETITION = "repetition"
    CONSISTENCY = "consistency"
    CONDITIONAL = "conditional"
    CAPITALIZATION = "capitalization"
    METRIC = "metric"
    SEQUENCE = "sequence"
    SCRIPT = "script"  # Excluded v1.0 (NFR-SEC-03.2)
    LLM_EVAL = "llm_eval"  # phraseturner extension
    TONE = "tone"  # phraseturner extension
    BRAND_VOICE = "brand_voice"  # phraseturner extension


class RuleLevel(StrEnum):
    """Rule severity levels matching Vale's level system.

    Implements AC-FR-PERSONA-02.4.
    """

    ERROR = "error"
    WARNING = "warning"
    SUGGESTION = "suggestion"


class Channel(StrEnum):
    """Supported communication channels for persona targeting.

    Implements AC-FR-PERSONA-03.6, AC-FR-PERSONA-03.7.
    """

    SLACK = "slack"
    EMAIL = "email"
    CONFLUENCE = "confluence"
    JIRA = "jira"
    PR_REVIEW = "pr-review"
    BLOG = "blog"
    DOCS = "docs"
    EXECUTIVE = "executive"
    FORK_BRIEF = "fork-brief"
    DECISION_NOTE = "decision-note"
    PANEL_VOTE = "panel-vote"


class RuleExample(BaseModel):
    """Example texts for rule validation.

    Valid examples should not trigger the rule; invalid examples should.
    Implements AC-FR-PERSONA-07.3.

    Attributes:
        valid: Texts that should pass the rule without triggering.
        invalid: Texts that should trigger the rule.
    """

    valid: list[str] = Field(default_factory=list)
    invalid: list[str] = Field(default_factory=list)


class AudienceConfig(BaseModel):
    """Target audience configuration.

    Implements AC-FR-PERSONA-03.6.

    Attributes:
        expertise_level: Audience expertise (e.g. beginner, intermediate, expert).
        domain: Subject domain (e.g. engineering, marketing, legal).
    """

    expertise_level: str | None = None
    domain: str | None = None


class HealthScoreWeights(BaseModel):
    """Per-persona weight overrides for health score dimensions.

    All weights must be in [0.0, 1.0] and sum to 1.0.
    Implements AC-FR-HEALTH-03.1, AC-FR-HEALTH-03.2.

    Attributes:
        readability: Weight for the readability dimension.
        naturalness: Weight for the naturalness dimension.
        vocabulary: Weight for the vocabulary dimension.
        semantic_preservation: Weight for the semantic preservation dimension.
        tone_compliance: Weight for the tone compliance dimension.
    """

    readability: float = Field(ge=0.0, le=1.0)
    naturalness: float = Field(ge=0.0, le=1.0)
    vocabulary: float = Field(ge=0.0, le=1.0)
    semantic_preservation: float = Field(ge=0.0, le=1.0)
    tone_compliance: float = Field(ge=0.0, le=1.0)


class ChannelOverride(BaseModel):
    """Per-channel overrides for tone dimensions and rule severity.

    Implements AC-FR-PERSONA-03.7.

    Attributes:
        tone: Optional tone dimension overrides for this channel.
        rule_severity: Rule ID to severity level overrides for this channel.
    """

    tone: ToneConfig | None = None
    rule_severity: dict[str, RuleLevel] = Field(default_factory=dict)


class RuleConfig(BaseModel):
    """Individual persona rule definition.

    Supports all 10 Vale rule types and 3 phraseturner extensions.
    Implements AC-FR-PERSONA-03.5, AC-FR-PERSONA-02.

    Attributes:
        id: Unique rule identifier within the persona.
        type: Rule type from the 13 supported types.
        level: Severity level (error, warning, suggestion).
        message: Human-readable message when the rule triggers.
        scope: Text scope for rule evaluation (text, sentence, paragraph, heading, raw).
        tokens: Token patterns for existence/substitution rules.
        raw: Raw regex patterns for existence rules.
        swap: Substitution map (pattern → replacement) for substitution rules.
        max: Maximum occurrence count for occurrence rules.
        either: Consistency enforcement map for consistency rules.
        match: Regex match pattern for capitalization/metric rules.
        metric: Formula identifier for metric rules.
        prompt: FLAN-T5 prompt template for llm_eval rules.
        target: Expected T5 output for llm_eval rules.
        tolerance: Confidence tolerance for llm_eval rules.
        min: Minimum threshold for tone dimension rules.
        dimension: Tone dimension name for tone rules.
        action: Vale action configuration (replace, edit, remove, suggest).
        examples: Example texts for rule validation.
        channel: Channel scope restriction for this rule.
    """

    id: str
    type: RuleType
    level: RuleLevel = RuleLevel.WARNING
    message: str | None = None
    scope: str = "text"
    # Vale fields
    tokens: list[str] | None = None
    raw: list[str] | None = None
    swap: dict[str, str] | None = None
    max: int | None = None
    either: dict[str, str] | None = None
    match: str | None = None
    metric: str | None = None
    # phraseturner extension fields
    prompt: str | None = None  # llm_eval
    target: str | None = None  # llm_eval
    tolerance: float | None = None  # llm_eval
    min: float | None = None  # tone threshold
    dimension: str | None = None  # tone dimension name
    action: dict[str, str] | None = None
    examples: RuleExample | None = None
    channel: Channel | None = None


class PersonaConfig(BaseModel):
    """Complete persona definition parsed from YAML.

    Parsed via ``yaml.safe_load`` (NFR-SEC-02.1).
    Implements AC-FR-PERSONA-03.1 through AC-FR-PERSONA-03.7.

    Attributes:
        name: Persona name (required, unique identifier).
        version: Semantic version string (e.g. ``1.0.0``).
        description: Human-readable persona description.
        author: Persona author name.
        locale: Locale code (e.g. ``en-GB``).
        channels: Communication channels this persona targets.
        audience: Target audience configuration.
        tags: Searchable tags for persona discovery.
        tone: 6-dimension tone configuration.
        brand_voice: Brand voice identity configuration.
        vocabulary: Approved and prohibited vocabulary.
        rules: List of analysis rules.
        channel_overrides: Per-channel tone and rule severity overrides.
        health_score_weights: Custom dimension weights for health scoring.
    """

    name: str
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    description: str | None = None
    author: str | None = None
    locale: str | None = None
    channels: list[Channel] = Field(default_factory=list)
    audience: AudienceConfig | None = None
    tags: list[str] = Field(default_factory=list)
    tone: ToneConfig = Field(default_factory=ToneConfig)
    brand_voice: BrandVoiceConfig | None = None
    vocabulary: VocabularyConfig = Field(default_factory=VocabularyConfig)
    rules: list[RuleConfig] = Field(default_factory=list)
    channel_overrides: dict[Channel, ChannelOverride] = Field(default_factory=dict)
    health_score_weights: HealthScoreWeights | None = None

    @field_validator("health_score_weights")
    @classmethod
    def validate_weights_sum(
        cls, v: HealthScoreWeights | None,
    ) -> HealthScoreWeights | None:
        """Validate that health score weights sum to 1.0.

        Implements AC-FR-HEALTH-03.2.

        Args:
            v: The health score weights to validate, or ``None``.

        Returns:
            The validated weights unchanged.

        Raises:
            ValueError: If weights do not sum to 1.0 (±0.001 tolerance).
        """
        if v is None:
            return v
        total = (
            v.readability
            + v.naturalness
            + v.vocabulary
            + v.semantic_preservation
            + v.tone_compliance
        )
        if abs(total - 1.0) > _WEIGHTS_SUM_TOLERANCE:
            msg = f"Weights must sum to 1.0, got {total:.3f}"
            raise ValueError(msg)
        return v
