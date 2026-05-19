"""Stage 5: Output formatting — flags, suggestions, and persona alignment.

Generates per-sentence quality flags, ranked improvement suggestions
(hints only, NEVER rewrites — CON-04), and persona alignment scores.

Implements FR-HEALTH-05, FR-HEALTH-06, CON-04.
Design reference: §4.7.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import structlog

from phraseturner.models.analysis import (
    Flag,
    PersonaAlignment,
    Suggestion,
    ToneDelta,
)
from phraseturner.personas.rules import RuleEvaluator, RuleMatch

if TYPE_CHECKING:
    from phraseturner.personas.schema import PersonaConfig

logger = structlog.get_logger()

# --- Constants ---

_LONG_SENTENCE_THRESHOLD = 30
"""Word count above which LONG_SENTENCE is raised. AC-FR-HEALTH-05.1."""

_SHORT_SENTENCE_THRESHOLD = 5
"""Word count below which SHORT_SENTENCE is raised. AC-FR-HEALTH-05.1."""

_HEDGE_COUNT_THRESHOLD = 2
"""Hedge count at or above which HIGH_HEDGE_COUNT is raised. AC-FR-HEALTH-05.1."""

_LOW_DENSITY_THRESHOLD = 0.35
"""Information density below which LOW_DENSITY is raised. AC-FR-HEALTH-05.1."""

_VAGUE_THRESHOLD = 0.25
"""Specificity below which VAGUE is raised. AC-FR-HEALTH-05.1."""

_LOW_COHERENCE_THRESHOLD = 0.10
"""Coherence-to-next below which LOW_COHERENCE is raised. AC-FR-HEALTH-05.1."""

_FORMAL_PERSONA_THRESHOLD = 0.7
"""Persona formality above which casual markers trigger CASUAL_IN_FORMAL."""

_CASUAL_PERSONA_THRESHOLD = 0.3
"""Persona formality below which formal markers trigger FORMAL_IN_CASUAL."""

_REDUNDANCY_JACCARD_THRESHOLD = 0.6
"""Jaccard similarity at or above which sentences are flagged as redundant."""

_DEFAULT_MAX_SUGGESTIONS = 5
"""Maximum number of suggestions returned. AC-FR-HEALTH-06.1."""

_IMPACT_ERROR = 0.9
"""Impact score for error-severity flags."""

_IMPACT_WARNING = 0.7
"""Impact score for warning-severity flags."""

_IMPACT_SUGGESTION = 0.4
"""Impact score for suggestion-severity flags."""

_TONE_DIMENSIONS = (
    "formality",
    "confidence",
    "warmth",
    "directness",
    "energy",
    "verbosity",
)
"""The 6 persona tone dimensions."""

# Regex for detecting contractions (casual markers).
_CONTRACTION_RE = re.compile(
    r"\b(?:can't|won't|don't|isn't|aren't|wasn't|weren't|hasn't|haven't"
    r"|hadn't|doesn't|didn't|couldn't|shouldn't|wouldn't|mustn't"
    r"|it's|he's|she's|that's|there's|here's|what's|who's"
    r"|I'm|you're|we're|they're|I've|you've|we've|they've"
    r"|I'll|you'll|he'll|she'll|we'll|they'll|I'd|you'd"
    r"|he'd|she'd|we'd|they'd)\b",
    re.IGNORECASE,
)

# Formal markers: Latin abbreviations, nominalisations, formal transitions.
_FORMAL_MARKER_RE = re.compile(
    r"\b(?:e\.g\.|i\.e\.|viz\.|cf\.|et al\.|ibid\."
    r"|furthermore|moreover|notwithstanding|henceforth"
    r"|aforementioned|hereinafter|pursuant|whereby"
    r"|utilise|utilize|facilitate|implement|commence"
    r"|subsequently|consequently|accordingly)\b",
    re.IGNORECASE,
)

# --- Hint templates (directives, NEVER rewrites — CON-04) ---

_HINT_MAP: dict[str, str] = {
    "LONG_SENTENCE": "Shorten this sentence — consider splitting into two",
    "SHORT_SENTENCE": "Expand this sentence with more detail or context",
    "PASSIVE_VOICE": "Replace passive voice with active construction",
    "HIGH_HEDGE_COUNT": "Remove hedging language to sound more confident",
    "LOW_DENSITY": "Add more content words — reduce filler and function words",
    "VAGUE": "Add specific details, numbers, or named entities",
    "LOW_COHERENCE": "Improve the transition to the next sentence",
    "AI_PATTERN": "Vary sentence structure to sound more natural",
    "AVOID_WORD_HIT": "Replace prohibited vocabulary with an approved alternative",
    "FORMAL_IN_CASUAL": "Use less formal language to match the casual persona",
    "CASUAL_IN_FORMAL": "Remove contractions and use formal register",
    "REDUNDANT": "Remove or merge this sentence — it repeats an earlier point",
}


# --- Flag generation helpers ---


def _has_formal_markers(text: str) -> bool:
    """Check whether text contains formal language markers."""
    return bool(_FORMAL_MARKER_RE.search(text))


def _has_contractions(text: str) -> bool:
    """Check whether text contains contractions (casual markers)."""
    return bool(_CONTRACTION_RE.search(text))


def _detect_redundant(
    sentences: list[dict[str, Any]],
) -> set[int]:
    """Detect sentence indices with high overlap to a preceding sentence.

    Uses a simple word-set Jaccard similarity to flag redundancy.

    Args:
        sentences: List of sentence data dicts with ``text`` keys.

    Returns:
        Set of sentence indices flagged as redundant.
    """
    redundant: set[int] = set()
    word_sets: list[set[str]] = []
    for sent in sentences:
        words = set(sent.get("text", "").lower().split())
        word_sets.append(words)

    for i in range(1, len(word_sets)):
        for j in range(i):
            union = word_sets[i] | word_sets[j]
            if not union:
                continue
            jaccard = len(word_sets[i] & word_sets[j]) / len(union)
            if jaccard >= _REDUNDANCY_JACCARD_THRESHOLD:
                redundant.add(i)
                break
    return redundant


def _check_length_flags(word_count: int) -> list[Flag]:
    """Check sentence length flags (LONG_SENTENCE, SHORT_SENTENCE)."""
    flags: list[Flag] = []
    if word_count > _LONG_SENTENCE_THRESHOLD:
        flags.append(
            Flag(
                code="LONG_SENTENCE",
                severity="warning",
                message=f"Sentence has {word_count} words (>{_LONG_SENTENCE_THRESHOLD})",
            )
        )
    if word_count < _SHORT_SENTENCE_THRESHOLD:
        flags.append(
            Flag(
                code="SHORT_SENTENCE",
                severity="suggestion",
                message=f"Sentence has only {word_count} words",
            )
        )
    return flags


def _check_quality_flags(sentence_data: dict[str, Any]) -> list[Flag]:
    """Check quality signal flags (LOW_DENSITY, VAGUE, LOW_COHERENCE, AI_PATTERN)."""
    flags: list[Flag] = []

    info_density = sentence_data.get("information_density")
    if info_density is not None and info_density < _LOW_DENSITY_THRESHOLD:
        flags.append(
            Flag(
                code="LOW_DENSITY",
                severity="warning",
                message=f"Low information density ({info_density:.2f})",
            )
        )

    specificity = sentence_data.get("specificity")
    if specificity is not None and specificity < _VAGUE_THRESHOLD:
        flags.append(
            Flag(
                code="VAGUE",
                severity="suggestion",
                message=f"Low specificity ({specificity:.2f})",
            )
        )

    coherence = sentence_data.get("coherence_to_next")
    if coherence is not None and coherence < _LOW_COHERENCE_THRESHOLD:
        flags.append(
            Flag(
                code="LOW_COHERENCE",
                severity="suggestion",
                message=f"Low coherence to next sentence ({coherence:.2f})",
            )
        )

    if sentence_data.get("ai_classification") == "likely-ai":
        flags.append(
            Flag(
                code="AI_PATTERN",
                severity="warning",
                message="Text classified as likely AI-generated",
            )
        )

    return flags


def _check_metric_flags(sentence_data: dict[str, Any]) -> list[Flag]:
    """Check metric-based flag conditions for a sentence. AC-FR-HEALTH-05.1.

    Args:
        sentence_data: Sentence metrics dict.

    Returns:
        List of metric-based flags.
    """
    word_count: int = sentence_data.get("word_count", 0)
    flags = _check_length_flags(word_count)

    if sentence_data.get("passive_voice", False):
        flags.append(
            Flag(
                code="PASSIVE_VOICE",
                severity="warning",
                message="Passive voice detected",
            )
        )

    hedge_count: int = sentence_data.get("hedge_count", 0)
    if hedge_count >= _HEDGE_COUNT_THRESHOLD:
        flags.append(
            Flag(
                code="HIGH_HEDGE_COUNT",
                severity="warning",
                message=f"High hedging ({hedge_count} hedge words)",
            )
        )

    flags.extend(_check_quality_flags(sentence_data))
    return flags


def _check_persona_flags(
    text: str,
    persona: PersonaConfig,
) -> list[Flag]:
    """Check persona-dependent flag conditions for a sentence.

    Handles AVOID_WORD_HIT, FORMAL_IN_CASUAL, CASUAL_IN_FORMAL.

    Args:
        text: The sentence text.
        persona: Persona configuration.

    Returns:
        List of persona-related flags.
    """
    flags: list[Flag] = []

    # AVOID_WORD_HIT — error  AC-FR-HEALTH-05.1
    if persona.vocabulary.prohibited:
        text_lower = text.lower()
        for word in persona.vocabulary.prohibited:
            if word.lower() in text_lower:
                flags.append(
                    Flag(
                        code="AVOID_WORD_HIT",
                        severity="error",
                        message=f"Prohibited word '{word}' detected",
                    )
                )
                break  # One flag per sentence for prohibited words

    # FORMAL_IN_CASUAL — error  AC-FR-HEALTH-05.1
    if persona.tone.formality < _CASUAL_PERSONA_THRESHOLD and _has_formal_markers(text):
        flags.append(
            Flag(
                code="FORMAL_IN_CASUAL",
                severity="error",
                message="Formal language detected in casual persona",
            )
        )

    # CASUAL_IN_FORMAL — error  AC-FR-HEALTH-05.1
    if persona.tone.formality > _FORMAL_PERSONA_THRESHOLD and _has_contractions(text):
        flags.append(
            Flag(
                code="CASUAL_IN_FORMAL",
                severity="error",
                message="Contractions detected in formal persona",
            )
        )

    return flags


# --- Main flag generation ---


def generate_flags(
    sentence_data: dict[str, Any],
    *,
    persona: PersonaConfig | None = None,
    is_redundant: bool = False,
) -> list[Flag]:
    """Generate quality flags for a single sentence.

    Checks 12 conditions and produces Flag objects with code, severity,
    and human-readable message. Implements FR-HEALTH-05.

    Args:
        sentence_data: Dict with sentence metrics (word_count, passive_voice,
            hedge_count, information_density, specificity, coherence_to_next,
            ai_classification, text).
        persona: Optional persona config for vocabulary and formality checks.
        is_redundant: Whether this sentence was flagged as redundant.

    Returns:
        List of Flag objects for the sentence.
    """
    flags = _check_metric_flags(sentence_data)

    # Persona-dependent flags.
    if persona is not None:
        text: str = sentence_data.get("text", "")
        flags.extend(_check_persona_flags(text, persona))

    # REDUNDANT — suggestion  AC-FR-HEALTH-05.1
    if is_redundant:
        flags.append(
            Flag(
                code="REDUNDANT",
                severity="suggestion",
                message="Sentence is highly similar to an earlier sentence",
            )
        )

    return flags


# --- Suggestion generation ---


def _impact_for_severity(severity: str) -> float:
    """Map flag severity to an impact score.

    Args:
        severity: One of ``error``, ``warning``, ``suggestion``.

    Returns:
        Impact score: 0.9 for error, 0.7 for warning, 0.4 for suggestion.
    """
    if severity == "error":
        return _IMPACT_ERROR
    if severity == "warning":
        return _IMPACT_WARNING
    return _IMPACT_SUGGESTION


def generate_suggestions(
    sentences: list[dict[str, Any]],
    flags: list[list[Flag]],
    *,
    max_suggestions: int = _DEFAULT_MAX_SUGGESTIONS,
) -> list[Suggestion]:
    """Generate ranked improvement suggestions from sentence flags.

    For each flag, produces a directive hint (NEVER a rewrite — CON-04).
    Suggestions are ranked by impact descending and capped at
    ``max_suggestions``. Implements FR-HEALTH-06.

    Args:
        sentences: List of sentence data dicts (used for indexing).
        flags: Per-sentence flag lists (parallel to ``sentences``).
        max_suggestions: Maximum suggestions to return (default 5).

    Returns:
        List of Suggestion objects sorted by impact (highest first).
    """
    candidates: list[Suggestion] = []

    for sent_idx, sent_flags in enumerate(flags):
        for flag in sent_flags:
            if flag.code in _HINT_MAP:
                hint = _HINT_MAP[flag.code]
            elif flag.code.startswith("RULE_"):
                # Actionable hint based on severity for rule-based flags.
                if flag.severity == "error":
                    hint = f"Remove or fix: {flag.message}"
                elif flag.severity == "warning":
                    hint = f"Consider rephrasing: {flag.message}"
                else:
                    hint = f"Review: {flag.message}"
            else:
                hint = f"Review issue: {flag.code}"
            impact = _impact_for_severity(flag.severity)
            candidates.append(
                Suggestion(
                    sentence_index=sent_idx,
                    flag_code=flag.code,
                    hint=hint,
                    impact=impact,
                )
            )

    # Sort by impact descending, then by sentence index for stability.
    candidates.sort(key=lambda s: (-s.impact, s.sentence_index))
    return candidates[:max_suggestions]


# --- Persona alignment ---


def compute_persona_alignment(
    tone_scores: dict[str, float],
    persona_config: PersonaConfig,
    rule_matches: list[dict[str, Any]],
    *,
    rule_passes: int | None = None,
) -> PersonaAlignment:
    """Compute persona alignment from tone scores and rule match results.

    Calculates tone deltas (target - actual) for each of the 6 dimensions,
    overall compliance as ``1.0 - mean(abs(deltas))`` clamped to [0.0, 1.0],
    and counts of rule violations vs passes.

    Args:
        tone_scores: Actual tone dimension values keyed by dimension name.
            Values should be in [0.0, 1.0].
        persona_config: The persona configuration with target tone values.
        rule_matches: List of rule match dicts, each with a ``level`` key
            (``error``, ``warning``, or ``suggestion``).

    Returns:
        PersonaAlignment with compliance score, tone deltas, and rule counts.
    """
    tone_deltas: dict[str, ToneDelta] = {}
    abs_deltas: list[float] = []

    target_tone = persona_config.tone
    for dim in _TONE_DIMENSIONS:
        target_val = getattr(target_tone, dim, 0.5)
        actual_val = tone_scores.get(dim, 0.5)
        delta = target_val - actual_val
        tone_deltas[dim] = ToneDelta(
            target=target_val,
            actual=actual_val,
            delta=delta,
        )
        abs_deltas.append(abs(delta))

    # Overall compliance: 1.0 - mean(abs(deltas)), clamped to [0.0, 1.0].
    mean_abs_delta = sum(abs_deltas) / len(abs_deltas) if abs_deltas else 0.0
    overall_compliance = max(0.0, min(1.0, 1.0 - mean_abs_delta))

    # Count rule violations (error or warning) vs passes.
    # rule_passes may be pre-computed by the caller (rules with zero violations).
    violation_levels = {"error", "warning"}
    rule_violations = sum(1 for m in rule_matches if m.get("level") in violation_levels)
    if rule_passes is None:
        rule_passes = len(rule_matches) - rule_violations

    return PersonaAlignment(
        overall_compliance=round(overall_compliance, 3),
        tone_deltas=tone_deltas,
        rule_violations=rule_violations,
        rule_passes=rule_passes,
    )


def _map_rule_matches_to_flags(
    rule_matches: list[RuleMatch],
    sentence_texts: list[str],
    all_flags: list[list[Flag]],
) -> None:
    """Map RuleMatch objects to per-sentence Flag objects.

    For each rule match, determines which sentence contains the matched
    text and appends a corresponding Flag to that sentence's flag list.
    If the matched text spans the full document or cannot be attributed
    to a single sentence, the flag is added to every sentence that
    contains the matched text.

    Args:
        rule_matches: Rule violation matches from the RuleEvaluator.
        sentence_texts: Pre-split sentence strings (parallel to all_flags).
        all_flags: Per-sentence flag lists to append to (mutated in place).
    """
    for match in rule_matches:
        # Substitute matched text into the rule message placeholder (%s).
        raw_message = match.message or ""
        resolved_message = raw_message.replace("%s", match.matched_text)
        flag = Flag(
            code=f"RULE_{match.rule_id}",
            severity=(
                match.level if match.level in {"error", "warning", "suggestion"} else "warning"
            ),
            message=resolved_message,
        )
        matched_lower = match.matched_text.lower()
        placed = False
        for idx, sent_text in enumerate(sentence_texts):
            if idx < len(all_flags) and matched_lower in sent_text.lower():
                all_flags[idx].append(flag)
                placed = True
        # If the match couldn't be placed (e.g. cross-sentence or
        # full-text scope), attach it to the first sentence as fallback.
        if not placed and all_flags:
            all_flags[0].append(flag)


# --- Main formatting function ---


# Module-level RuleEvaluator instance (stateless, safe to reuse).
_rule_evaluator = RuleEvaluator()


def format_output(
    analysis_data: dict[str, Any],
    persona: PersonaConfig | None = None,
    *,
    text: str = "",
    sentences: list[str] | None = None,
) -> tuple[list[list[Flag]], list[Suggestion], PersonaAlignment | None]:
    """Orchestrate Stage 5 output formatting.

    Generates per-sentence flags, ranked suggestions, and optional
    persona alignment. Implements FR-HEALTH-05, FR-HEALTH-06.

    Args:
        analysis_data: Dict containing:
            - ``sentences``: list of sentence data dicts with metrics.
            - ``tone_scores``: dict of actual tone dimension values (optional).
            - ``rule_matches``: list of rule match dicts (optional).
        persona: Optional persona config for persona-aware flags and alignment.
        text: Full input text (used for rule evaluation when persona provided).
        sentences: Pre-split sentence strings (used for rule evaluation).

    Returns:
        Tuple of (per-sentence flags, suggestions, persona alignment or None).
    """
    sentence_dicts: list[dict[str, Any]] = analysis_data.get("sentences", [])
    sentence_texts: list[str] = sentences or [s.get("text", "") for s in sentence_dicts]
    full_text = text or " ".join(sentence_texts)

    # Detect redundant sentences across the full document.
    redundant_indices = _detect_redundant(sentence_dicts)

    # Generate flags for each sentence.
    all_flags: list[list[Flag]] = []
    for idx, sent in enumerate(sentence_dicts):
        sent_flags = generate_flags(
            sent,
            persona=persona,
            is_redundant=idx in redundant_indices,
        )
        all_flags.append(sent_flags)

    # Generate ranked suggestions from all flags.
    suggestions = generate_suggestions(sentence_dicts, all_flags)

    # Compute persona alignment if persona is provided.
    alignment: PersonaAlignment | None = None
    if persona is not None:
        tone_scores: dict[str, float] = analysis_data.get("tone_scores", {})

        # C1: Evaluate persona rules via RuleEvaluator.
        # rule_matches contains only violations; rule_passes counts rules
        # that produced zero violations. AC-FR-HEALTH-05.1.
        rule_matches: list[dict[str, Any]] = []
        all_rule_matches: list[RuleMatch] = []
        rule_violations_count = 0
        for rule in persona.rules:
            try:
                matches = _rule_evaluator.evaluate(rule, full_text, sentence_texts)
                if matches:
                    rule_violations_count += 1
                    all_rule_matches.extend(matches)
                    for m in matches:
                        rule_matches.append({"level": m.level, "rule_id": m.rule_id})
            except NotImplementedError:
                # Script rules are excluded in v1.0 (NFR-SEC-03.2)
                pass
            except Exception:
                logger.debug("rule_evaluation_error", rule_id=rule.id)

        # Map RuleMatch objects to per-sentence Flag objects so that
        # rule violations appear in the sentence-level flags list.
        _map_rule_matches_to_flags(all_rule_matches, sentence_texts, all_flags)

        # Re-generate suggestions now that rule violation flags are included.
        suggestions = generate_suggestions(sentence_dicts, all_flags)

        rule_passes = len(persona.rules) - rule_violations_count
        alignment = compute_persona_alignment(
            tone_scores,
            persona,
            rule_matches,
            rule_passes=rule_passes,
        )

    return all_flags, suggestions, alignment
