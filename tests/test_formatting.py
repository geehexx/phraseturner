"""Tests for Stage 5: Output formatting — flags, suggestions, persona alignment.

Tests the formatting pipeline module that implements FR-HEALTH-05, FR-HEALTH-06.
"""

from __future__ import annotations

from phraseturner.models.analysis import Flag, PersonaAlignment
from phraseturner.personas.schema import (
    PersonaConfig,
    ToneConfig,
    VocabularyConfig,
)
from phraseturner.pipeline.formatting import (
    compute_persona_alignment,
    format_output,
    generate_flags,
    generate_suggestions,
)


def _make_persona(
    *,
    formality: float = 0.5,
    prohibited: list[str] | None = None,
) -> PersonaConfig:
    """Create a minimal PersonaConfig for testing."""
    return PersonaConfig(
        name="test-persona",
        version="1.0.0",
        tone=ToneConfig(formality=formality),
        vocabulary=VocabularyConfig(
            prohibited=prohibited or [],
        ),
    )


# --- generate_flags tests ---


class TestGenerateFlags:
    """Tests for generate_flags function."""

    def test_long_sentence_flag(self) -> None:
        data = {"word_count": 35, "text": "a " * 35}
        flags = generate_flags(data)
        codes = [f.code for f in flags]
        assert "LONG_SENTENCE" in codes
        flag = next(f for f in flags if f.code == "LONG_SENTENCE")
        assert flag.severity == "warning"

    def test_short_sentence_flag(self) -> None:
        data = {"word_count": 3, "text": "Hello there friend"}
        flags = generate_flags(data)
        codes = [f.code for f in flags]
        assert "SHORT_SENTENCE" in codes
        flag = next(f for f in flags if f.code == "SHORT_SENTENCE")
        assert flag.severity == "suggestion"

    def test_no_short_flag_at_threshold(self) -> None:
        data = {"word_count": 5, "text": "This is a test sentence"}
        flags = generate_flags(data)
        codes = [f.code for f in flags]
        assert "SHORT_SENTENCE" not in codes

    def test_passive_voice_flag(self) -> None:
        data = {"word_count": 10, "text": "The ball was thrown", "passive_voice": True}
        flags = generate_flags(data)
        codes = [f.code for f in flags]
        assert "PASSIVE_VOICE" in codes

    def test_high_hedge_count_flag(self) -> None:
        data = {"word_count": 10, "text": "test", "hedge_count": 3}
        flags = generate_flags(data)
        codes = [f.code for f in flags]
        assert "HIGH_HEDGE_COUNT" in codes

    def test_hedge_count_at_threshold(self) -> None:
        data = {"word_count": 10, "text": "test", "hedge_count": 2}
        flags = generate_flags(data)
        codes = [f.code for f in flags]
        assert "HIGH_HEDGE_COUNT" in codes

    def test_low_density_flag(self) -> None:
        data = {"word_count": 10, "text": "test", "information_density": 0.2}
        flags = generate_flags(data)
        codes = [f.code for f in flags]
        assert "LOW_DENSITY" in codes

    def test_vague_flag(self) -> None:
        data = {"word_count": 10, "text": "test", "specificity": 0.1}
        flags = generate_flags(data)
        codes = [f.code for f in flags]
        assert "VAGUE" in codes

    def test_low_coherence_flag(self) -> None:
        data = {"word_count": 10, "text": "test", "coherence_to_next": 0.05}
        flags = generate_flags(data)
        codes = [f.code for f in flags]
        assert "LOW_COHERENCE" in codes

    def test_ai_pattern_flag(self) -> None:
        data = {"word_count": 10, "text": "test", "ai_classification": "likely-ai"}
        flags = generate_flags(data)
        codes = [f.code for f in flags]
        assert "AI_PATTERN" in codes

    def test_avoid_word_hit_flag(self) -> None:
        persona = _make_persona(prohibited=["synergy"])
        data = {"word_count": 10, "text": "We need more synergy here"}
        flags = generate_flags(data, persona=persona)
        codes = [f.code for f in flags]
        assert "AVOID_WORD_HIT" in codes
        flag = next(f for f in flags if f.code == "AVOID_WORD_HIT")
        assert flag.severity == "error"

    def test_formal_in_casual_flag(self) -> None:
        persona = _make_persona(formality=0.1)
        data = {"word_count": 10, "text": "Furthermore, this is important"}
        flags = generate_flags(data, persona=persona)
        codes = [f.code for f in flags]
        assert "FORMAL_IN_CASUAL" in codes

    def test_casual_in_formal_flag(self) -> None:
        persona = _make_persona(formality=0.9)
        data = {"word_count": 10, "text": "We can't do this"}
        flags = generate_flags(data, persona=persona)
        codes = [f.code for f in flags]
        assert "CASUAL_IN_FORMAL" in codes

    def test_redundant_flag(self) -> None:
        data = {"word_count": 10, "text": "test"}
        flags = generate_flags(data, is_redundant=True)
        codes = [f.code for f in flags]
        assert "REDUNDANT" in codes

    def test_no_flags_for_clean_sentence(self) -> None:
        data = {"word_count": 15, "text": "A perfectly normal sentence here"}
        flags = generate_flags(data)
        assert flags == []

    def test_no_persona_flags_without_persona(self) -> None:
        data = {"word_count": 10, "text": "Furthermore, we can't do this"}
        flags = generate_flags(data)
        persona_codes = {"AVOID_WORD_HIT", "FORMAL_IN_CASUAL", "CASUAL_IN_FORMAL"}
        assert not any(f.code in persona_codes for f in flags)


# --- generate_suggestions tests ---


class TestGenerateSuggestions:
    """Tests for generate_suggestions function."""

    def test_suggestions_ranked_by_impact(self) -> None:
        sentences = [{"text": "a"}, {"text": "b"}]
        flags = [
            [Flag(code="VAGUE", severity="suggestion", message="vague")],
            [Flag(code="AVOID_WORD_HIT", severity="error", message="bad word")],
        ]
        suggestions = generate_suggestions(sentences, flags)
        assert suggestions[0].flag_code == "AVOID_WORD_HIT"
        assert suggestions[0].impact > suggestions[1].impact

    def test_max_suggestions_cap(self) -> None:
        sentences = [{"text": "a"}]
        flags = [
            [Flag(code=f"FLAG_{i}", severity="warning", message=f"msg {i}") for i in range(10)],
        ]
        suggestions = generate_suggestions(sentences, flags, max_suggestions=3)
        assert len(suggestions) <= 3

    def test_default_max_is_five(self) -> None:
        sentences = [{"text": "a"}]
        flags = [
            [Flag(code=f"FLAG_{i}", severity="warning", message=f"msg {i}") for i in range(10)],
        ]
        suggestions = generate_suggestions(sentences, flags)
        assert len(suggestions) <= 5

    def test_empty_flags_produce_no_suggestions(self) -> None:
        sentences = [{"text": "a"}, {"text": "b"}]
        flags: list[list[Flag]] = [[], []]
        suggestions = generate_suggestions(sentences, flags)
        assert suggestions == []

    def test_hints_are_directives_not_rewrites(self) -> None:
        """CON-04: suggestions must be hints, never rewrites."""
        sentences = [{"text": "a"}]
        flags = [
            [Flag(code="LONG_SENTENCE", severity="warning", message="too long")],
        ]
        suggestions = generate_suggestions(sentences, flags)
        assert len(suggestions) == 1
        # Hint should be a directive, not contain the original sentence text.
        assert "Shorten" in suggestions[0].hint

    def test_impact_scores_by_severity(self) -> None:
        sentences = [{"text": "a"}, {"text": "b"}, {"text": "c"}]
        flags = [
            [Flag(code="AVOID_WORD_HIT", severity="error", message="e")],
            [Flag(code="PASSIVE_VOICE", severity="warning", message="w")],
            [Flag(code="VAGUE", severity="suggestion", message="s")],
        ]
        suggestions = generate_suggestions(sentences, flags)
        error_s = next(s for s in suggestions if s.flag_code == "AVOID_WORD_HIT")
        warning_s = next(s for s in suggestions if s.flag_code == "PASSIVE_VOICE")
        suggestion_s = next(s for s in suggestions if s.flag_code == "VAGUE")
        assert error_s.impact == 0.9
        assert warning_s.impact == 0.7
        assert suggestion_s.impact == 0.4


# --- compute_persona_alignment tests ---


class TestComputePersonaAlignment:
    """Tests for compute_persona_alignment function."""

    def test_perfect_alignment(self) -> None:
        persona = _make_persona(formality=0.5)
        tone_scores = {
            "formality": 0.5,
            "confidence": 0.5,
            "warmth": 0.5,
            "directness": 0.5,
            "energy": 0.5,
            "verbosity": 0.5,
        }
        alignment = compute_persona_alignment(tone_scores, persona, [])
        assert alignment.overall_compliance == 1.0
        assert alignment.rule_violations == 0
        assert alignment.rule_passes == 0

    def test_tone_deltas_computed(self) -> None:
        persona = PersonaConfig(
            name="test",
            version="1.0.0",
            tone=ToneConfig(formality=0.8, warmth=0.2),
        )
        tone_scores = {"formality": 0.3, "warmth": 0.7}
        alignment = compute_persona_alignment(tone_scores, persona, [])
        assert alignment.tone_deltas["formality"].target == 0.8
        assert alignment.tone_deltas["formality"].actual == 0.3
        assert abs(alignment.tone_deltas["formality"].delta - 0.5) < 0.001

    def test_rule_violations_counted(self) -> None:
        persona = _make_persona()
        rules = [
            {"level": "error"},
            {"level": "warning"},
            {"level": "suggestion"},
        ]
        alignment = compute_persona_alignment({}, persona, rules)
        assert alignment.rule_violations == 2
        assert alignment.rule_passes == 1

    def test_compliance_clamped_to_zero(self) -> None:
        """When all deltas are maximal, compliance should be 0.0."""
        persona = PersonaConfig(
            name="test",
            version="1.0.0",
            tone=ToneConfig(
                formality=1.0, confidence=1.0, warmth=1.0,
                directness=1.0, energy=1.0, verbosity=1.0,
            ),
        )
        tone_scores = {
            "formality": 0.0, "confidence": 0.0, "warmth": 0.0,
            "directness": 0.0, "energy": 0.0, "verbosity": 0.0,
        }
        alignment = compute_persona_alignment(tone_scores, persona, [])
        assert alignment.overall_compliance == 0.0


# --- format_output tests ---


class TestFormatOutput:
    """Tests for the main format_output orchestrator."""

    def test_basic_output_structure(self) -> None:
        analysis_data = {
            "sentences": [
                {"word_count": 35, "text": "a " * 35},
                {"word_count": 8, "text": "Short and sweet sentence here now"},
            ],
        }
        all_flags, suggestions, alignment = format_output(analysis_data)
        assert len(all_flags) == 2
        assert isinstance(suggestions, list)
        assert alignment is None

    def test_persona_alignment_returned(self) -> None:
        persona = _make_persona()
        analysis_data = {
            "sentences": [{"word_count": 10, "text": "test"}],
            "tone_scores": {"formality": 0.5},
            "rule_matches": [],
        }
        _, _, alignment = format_output(analysis_data, persona=persona)
        assert alignment is not None
        assert isinstance(alignment, PersonaAlignment)

    def test_redundant_detection(self) -> None:
        analysis_data = {
            "sentences": [
                {"word_count": 10, "text": "the quick brown fox jumps over the lazy dog"},
                {"word_count": 10, "text": "the quick brown fox jumps over the lazy dog"},
            ],
        }
        all_flags, _, _ = format_output(analysis_data)
        # Second sentence should be flagged as redundant.
        codes_1 = [f.code for f in all_flags[1]]
        assert "REDUNDANT" in codes_1

    def test_empty_sentences(self) -> None:
        analysis_data: dict[str, list[dict[str, str]]] = {"sentences": []}
        all_flags, suggestions, alignment = format_output(analysis_data)
        assert all_flags == []
        assert suggestions == []
        assert alignment is None
