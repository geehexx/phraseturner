"""Persona output data models for phraseturner.

Implements §7.3 of the design specification.
Models for persona tool responses — summaries, details, creation results,
and validation results.

Implements FR-TOOL-02, FR-TOOL-03, FR-TOOL-04, FR-TOOL-05.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from phraseturner.personas.schema import (
        BrandVoiceConfig,
        ChannelOverride,
        HealthScoreWeights,
        RuleConfig,
        ToneConfig,
        VocabularyConfig,
    )


class PersonaSummary(BaseModel):
    """Summary of a persona returned by the ``list_personas`` tool.

    Implements FR-TOOL-02.

    Attributes:
        name: Persona name (unique within its tier).
        description: Optional human-readable description.
        tags: Categorisation tags for filtering.
        channels: Communication channels this persona targets.
        tier: Directory tier — ``built-in``, ``remote``, ``user``, or ``project``.
        version: Semantic version string (e.g. ``1.0.0``).
    """

    name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    tier: str  # built-in | remote | user | project
    version: str


class PersonaDetail(BaseModel):
    """Full persona definition returned by the ``get_persona`` tool.

    Implements FR-TOOL-03.

    Attributes:
        name: Persona name.
        version: Semantic version string.
        description: Optional human-readable description.
        tone: Tone configuration with 6 dimensions (0.0-1.0 each).
        brand_voice: Optional brand voice configuration.
        vocabulary: Vocabulary configuration (approved/prohibited word lists).
        rules: List of rule configurations.
        channel_overrides: Per-channel overrides keyed by channel name.
        health_score_weights: Optional per-persona health score weights.
        tier: Directory tier — ``built-in``, ``remote``, ``user``, or ``project``.
    """

    name: str
    version: str
    description: str | None = None
    tone: ToneConfig | None = None
    brand_voice: BrandVoiceConfig | None = None
    vocabulary: VocabularyConfig | None = None
    rules: list[RuleConfig] = Field(default_factory=list)
    channel_overrides: dict[str, ChannelOverride] = Field(default_factory=dict)
    health_score_weights: HealthScoreWeights | None = None
    tier: str


class ValidationError(BaseModel):
    """A single validation error or warning from persona validation.

    Implements FR-TOOL-05.

    Attributes:
        path: JSON path to the invalid field (e.g. ``tone.formality``).
        code: Machine-readable error code (e.g. ``INVALID_RANGE``).
        message: Human-readable description of the validation issue.
    """

    path: str
    code: str
    message: str


class ValidationResult(BaseModel):
    """Result of persona YAML validation.

    Implements FR-TOOL-05.

    Attributes:
        valid: Whether the persona YAML passed all validation checks.
        errors: List of validation errors (schema violations).
        warnings: List of validation warnings (non-blocking issues).
    """

    valid: bool
    errors: list[ValidationError] = Field(default_factory=list)
    warnings: list[ValidationError] = Field(default_factory=list)


class PersonaCreateResult(BaseModel):
    """Result of creating a new persona via the ``create_persona`` tool.

    Implements FR-TOOL-04.

    Attributes:
        name: Name of the created persona.
        file_path: Filesystem path where the persona YAML was written.
        validation: Validation result for the created persona.
    """

    name: str
    file_path: str
    validation: ValidationResult
