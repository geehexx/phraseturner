"""Tests for FLAN-T5 confidence thresholding and label validation.

Requirements: FR-T5-04
Design: §5.5
"""

from __future__ import annotations

from phraseturner.t5.prompts import (
    AI_PATTERN_DETECTION,
    CORE_MEANING,
    PARAPHRASE_HINTS,
    PERSONA_COMPLIANCE,
    SENTENCE_FUNCTION,
    STYLE_CLASSIFICATION,
)
from phraseturner.t5.validation import (
    T5Output,
    parse_persona_compliance_output,
    parse_tone_output,
    validate_and_threshold,
)

# -----------------------------------------------------------------------
# validate_and_threshold -- classification tasks
# -----------------------------------------------------------------------


class TestValidateAndThresholdClassification:
    """Tests for classification tasks with valid_labels and thresholds."""

    def test_valid_label_above_threshold(self) -> None:
        """Valid label with sufficient confidence passes through."""
        result = validate_and_threshold("formal", 0.80, STYLE_CLASSIFICATION)

        assert result == T5Output(label="formal", confidence=0.80, is_fallback=False)

    def test_valid_label_at_threshold(self) -> None:
        """Confidence exactly at threshold passes."""
        result = validate_and_threshold("formal", 0.65, STYLE_CLASSIFICATION)

        assert result == T5Output(label="formal", confidence=0.65, is_fallback=False)

    def test_valid_label_below_threshold(self) -> None:
        """Valid label below threshold falls back. AC-FR-T5-04.3."""
        result = validate_and_threshold("formal", 0.50, STYLE_CLASSIFICATION)

        assert result == T5Output(label="neutral", confidence=0.0, is_fallback=True)

    def test_invalid_label_falls_back(self) -> None:
        """Label not in valid_labels triggers fallback."""
        result = validate_and_threshold("unknown-style", 0.90, STYLE_CLASSIFICATION)

        assert result == T5Output(label="neutral", confidence=0.0, is_fallback=True)

    def test_normalises_whitespace_and_case(self) -> None:
        """Raw output is stripped and lowercased before validation."""
        result = validate_and_threshold("  Formal  ", 0.80, STYLE_CLASSIFICATION)

        assert result.label == "formal"
        assert not result.is_fallback

    def test_ai_pattern_threshold_0_55(self) -> None:
        """AI pattern detection uses 0.55 threshold."""
        above = validate_and_threshold("hedge-stacking", 0.56, AI_PATTERN_DETECTION)
        below = validate_and_threshold("hedge-stacking", 0.54, AI_PATTERN_DETECTION)

        assert not above.is_fallback
        assert below.is_fallback
        assert below.label == "none-obvious"

    def test_sentence_function_threshold_0_60(self) -> None:
        """Sentence function uses 0.60 threshold."""
        above = validate_and_threshold("claim", 0.61, SENTENCE_FUNCTION)
        below = validate_and_threshold("claim", 0.59, SENTENCE_FUNCTION)

        assert not above.is_fallback
        assert below.is_fallback
        assert below.label == "background"

    def test_persona_compliance_threshold_0_65(self) -> None:
        """Persona compliance uses 0.65 threshold."""
        above = validate_and_threshold("compliant", 0.66, PERSONA_COMPLIANCE)
        below = validate_and_threshold("compliant", 0.64, PERSONA_COMPLIANCE)

        assert not above.is_fallback
        assert below.is_fallback
        assert below.label == "compliant"

    def test_all_style_labels_accepted(self) -> None:
        """All 3 style labels are valid."""
        for label in ["formal", "informal", "neutral"]:
            result = validate_and_threshold(label, 0.90, STYLE_CLASSIFICATION)
            assert result.label == label
            assert not result.is_fallback

    def test_all_ai_pattern_labels_accepted(self) -> None:
        """All 7 AI pattern labels are valid."""
        for label in AI_PATTERN_DETECTION.valid_labels or []:
            result = validate_and_threshold(label, 0.90, AI_PATTERN_DETECTION)
            assert result.label == label
            assert not result.is_fallback

    def test_all_function_labels_accepted(self) -> None:
        """All 5 sentence function labels are valid."""
        for label in SENTENCE_FUNCTION.valid_labels or []:
            result = validate_and_threshold(label, 0.90, SENTENCE_FUNCTION)
            assert result.label == label
            assert not result.is_fallback


# -----------------------------------------------------------------------
# validate_and_threshold -- free-form tasks
# -----------------------------------------------------------------------


class TestValidateAndThresholdFreeForm:
    """Tests for free-form tasks (no valid_labels)."""

    def test_paraphrase_hints_passthrough(self) -> None:
        """Free-form tasks return output as-is."""
        result = validate_and_threshold("Use shorter sentences", 0.30, PARAPHRASE_HINTS)

        assert result.label == "Use shorter sentences"
        assert result.confidence == 0.30
        assert not result.is_fallback

    def test_core_meaning_passthrough(self) -> None:
        """Core meaning extraction returns stripped output."""
        result = validate_and_threshold("  factors were considered  ", 0.45, CORE_MEANING)

        assert result.label == "factors were considered"
        assert result.confidence == 0.45
        assert not result.is_fallback

    def test_free_form_low_confidence_still_passes(self) -> None:
        """Free-form tasks have no threshold -- low confidence passes."""
        result = validate_and_threshold("some hint", 0.01, PARAPHRASE_HINTS)

        assert not result.is_fallback


# -----------------------------------------------------------------------
# parse_tone_output
# -----------------------------------------------------------------------


class TestParseToneOutput:
    """Tests for multi-dimension tone assessment parsing."""

    def test_standard_three_dimensions(self) -> None:
        """Parses standard 3-dimension output."""
        result = parse_tone_output(
            "formality: high, confidence: medium, directness: low",
            confidence=0.75,
        )

        assert len(result) == 3
        assert result["formality"].label == "high"
        assert result["confidence"].label == "medium"
        assert result["directness"].label == "low"
        assert all(not v.is_fallback for v in result.values())

    def test_below_threshold_all_fallback(self) -> None:
        """All dimensions fall back when confidence is below threshold."""
        result = parse_tone_output(
            "formality: high, confidence: medium, directness: low",
            confidence=0.50,
            threshold=0.60,
        )

        assert all(v.is_fallback for v in result.values())
        assert all(v.label == "medium" for v in result.values())
        assert all(v.confidence == 0.0 for v in result.values())

    def test_invalid_value_falls_back(self) -> None:
        """Invalid dimension value triggers fallback for that dimension."""
        result = parse_tone_output(
            "formality: extreme, confidence: medium",
            confidence=0.80,
        )

        assert result["formality"].is_fallback
        assert result["formality"].label == "medium"
        assert not result["confidence"].is_fallback
        assert result["confidence"].label == "medium"

    def test_empty_output_returns_empty_dict(self) -> None:
        """Empty or unparseable output returns empty dict."""
        result = parse_tone_output("", confidence=0.80)

        assert result == {}

    def test_at_threshold_passes(self) -> None:
        """Confidence exactly at threshold passes."""
        result = parse_tone_output(
            "formality: high",
            confidence=0.60,
            threshold=0.60,
        )

        assert not result["formality"].is_fallback

    def test_equals_sign_separator(self) -> None:
        """Supports '=' as dimension separator."""
        result = parse_tone_output(
            "formality=high, directness=low",
            confidence=0.80,
        )

        assert result["formality"].label == "high"
        assert result["directness"].label == "low"


# -----------------------------------------------------------------------
# parse_persona_compliance_output
# -----------------------------------------------------------------------


class TestParsePersonaComplianceOutput:
    """Tests for persona compliance parsing."""

    def test_compliant_no_issue(self) -> None:
        """Compliant output with no issue description."""
        output, issue = parse_persona_compliance_output("compliant", 0.80)

        assert output.label == "compliant"
        assert output.confidence == 0.80
        assert not output.is_fallback
        assert issue is None

    def test_major_violation_with_issue(self) -> None:
        """Major violation with issue description."""
        output, issue = parse_persona_compliance_output(
            "major-violation: formal register in casual persona",
            0.90,
        )

        assert output.label == "major-violation"
        assert not output.is_fallback
        assert issue == "formal register in casual persona"

    def test_minor_violation_with_issue(self) -> None:
        """Minor violation with issue description."""
        output, issue = parse_persona_compliance_output(
            "minor-violation: slightly formal tone",
            0.70,
        )

        assert output.label == "minor-violation"
        assert issue == "slightly formal tone"

    def test_below_threshold_falls_back(self) -> None:
        """Below threshold falls back to compliant."""
        output, issue = parse_persona_compliance_output(
            "major-violation: some issue",
            0.50,
            threshold=0.65,
        )

        assert output.label == "compliant"
        assert output.confidence == 0.0
        assert output.is_fallback
        assert issue is None

    def test_invalid_label_falls_back(self) -> None:
        """Invalid label falls back to compliant."""
        output, issue = parse_persona_compliance_output(
            "unknown-label: some issue",
            0.90,
        )

        assert output.label == "compliant"
        assert output.is_fallback
        assert issue is None

    def test_empty_output_falls_back(self) -> None:
        """Empty output falls back."""
        output, issue = parse_persona_compliance_output("", 0.90)

        assert output.is_fallback
        assert issue is None

    def test_at_threshold_passes(self) -> None:
        """Confidence exactly at threshold passes."""
        output, _issue = parse_persona_compliance_output(
            "compliant",
            0.65,
            threshold=0.65,
        )

        assert not output.is_fallback

    def test_whitespace_handling(self) -> None:
        """Handles leading/trailing whitespace."""
        output, issue = parse_persona_compliance_output(
            "  major-violation:  formal register  ",
            0.80,
        )

        assert output.label == "major-violation"
        assert issue == "formal register"
