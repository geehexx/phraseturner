"""phraseturner persona system — 4-tier directory, YAML rules, semantic search."""

from __future__ import annotations

from phraseturner.personas.index import (
    TIER_BUILTIN,
    TIER_PROJECT,
    TIER_REMOTE,
    TIER_USER,
    PersonaIndex,
    get_persona_directories,
)
from phraseturner.personas.rules import (
    RuleEvaluator,
    RuleMatch,
)
from phraseturner.personas.schema import (
    AudienceConfig,
    BrandVoiceConfig,
    Channel,
    ChannelOverride,
    HealthScoreWeights,
    PersonaConfig,
    RuleConfig,
    RuleExample,
    RuleLevel,
    RuleType,
    ToneConfig,
    VocabularyConfig,
)
from phraseturner.personas.services import (
    create_persona,
    validate_persona,
)
from phraseturner.personas.validation import (
    PersonaValidator,
)

__all__ = [
    "TIER_BUILTIN",
    "TIER_PROJECT",
    "TIER_REMOTE",
    "TIER_USER",
    "AudienceConfig",
    "BrandVoiceConfig",
    "Channel",
    "ChannelOverride",
    "HealthScoreWeights",
    "PersonaConfig",
    "PersonaIndex",
    "PersonaValidator",
    "RuleConfig",
    "RuleEvaluator",
    "RuleExample",
    "RuleLevel",
    "RuleMatch",
    "RuleType",
    "ToneConfig",
    "VocabularyConfig",
    "create_persona",
    "get_persona_directories",
    "validate_persona",
]
