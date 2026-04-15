"""Tests for persona validation with structured error codes.

Tests PersonaValidator against all error codes defined in section 3.6.
Requirements: FR-PERSONA-07, NFR-SEC-03, NFR-SEC-05.
"""

from __future__ import annotations

import textwrap

import pytest

from phraseturner.personas.validation import (
    DUPLICATE_RULE_ID,
    EXAMPLE_MISMATCH,
    INVALID_ENUM_VALUE,
    INVALID_FIELD_TYPE,
    INVALID_RANGE,
    INVALID_REGEX,
    INVALID_RULE_TYPE,
    INVALID_SEMVER,
    INVALID_WEIGHTS_SUM,
    INVALID_YAML,
    MISSING_REQUIRED_FIELD,
    SECRET_DETECTED,
    PersonaValidator,
)

VALID_MINIMAL_YAML = textwrap.dedent("""\
    name: test-persona
    version: "1.0.0"
""")

VALID_FULL_YAML = textwrap.dedent("""\
    name: test-persona
    version: "1.0.0"
    description: A test persona
    tone:
      formality: 0.3
      warmth: 0.8
    rules:
      - id: no-jargon
        type: existence
        level: warning
        tokens:
          - synergy
          - leverage
""")


@pytest.fixture
def validator() -> PersonaValidator:
    return PersonaValidator()


class TestValidYaml:
    """Test that valid YAML passes validation."""

    def test_minimal_valid(self, validator: PersonaValidator) -> None:
        result = validator.validate_yaml(VALID_MINIMAL_YAML)
        assert result.valid
        assert result.errors == []

    def test_full_valid(self, validator: PersonaValidator) -> None:
        result = validator.validate_yaml(VALID_FULL_YAML)
        assert result.valid
        assert result.errors == []


class TestInvalidYaml:
    """Test INVALID_YAML error code."""

    def test_malformed_yaml(self, validator: PersonaValidator) -> None:
        result = validator.validate_yaml("{{invalid: yaml: [")
        assert not result.valid
        assert any(e.code == INVALID_YAML for e in result.errors)

    def test_non_mapping_yaml(self, validator: PersonaValidator) -> None:
        result = validator.validate_yaml("- just\n- a\n- list")
        assert not result.valid
        assert any(e.code == INVALID_YAML for e in result.errors)

    def test_scalar_yaml(self, validator: PersonaValidator) -> None:
        result = validator.validate_yaml("just a string")
        assert not result.valid
        assert any(e.code == INVALID_YAML for e in result.errors)


class TestMissingRequiredField:
    """Test MISSING_REQUIRED_FIELD error code."""

    def test_missing_name(self, validator: PersonaValidator) -> None:
        result = validator.validate_yaml('version: "1.0.0"')
        assert not result.valid
        assert any(
            e.code == MISSING_REQUIRED_FIELD and "name" in e.path
            for e in result.errors
        )

    def test_missing_version(self, validator: PersonaValidator) -> None:
        result = validator.validate_yaml("name: test")
        assert not result.valid
        assert any(
            e.code == MISSING_REQUIRED_FIELD and "version" in e.path
            for e in result.errors
        )

    def test_missing_both(self, validator: PersonaValidator) -> None:
        result = validator.validate_yaml("description: hello")
        assert not result.valid
        missing_codes = [
            e for e in result.errors
            if e.code == MISSING_REQUIRED_FIELD
        ]
        assert len(missing_codes) >= 2


class TestInvalidFieldType:
    """Test INVALID_FIELD_TYPE error code."""

    def test_name_not_string(self, validator: PersonaValidator) -> None:
        yaml_content = 'name: 123\nversion: "1.0.0"'
        result = validator.validate_yaml(yaml_content)
        assert not result.valid
        assert any(e.code == INVALID_FIELD_TYPE for e in result.errors)

    def test_rules_not_list(self, validator: PersonaValidator) -> None:
        yaml_content = textwrap.dedent("""\
            name: test
            version: "1.0.0"
            rules: not-a-list
        """)
        result = validator.validate_yaml(yaml_content)
        assert not result.valid
        assert any(e.code == INVALID_FIELD_TYPE for e in result.errors)


class TestInvalidEnumValue:
    """Test INVALID_ENUM_VALUE error code."""

    def test_invalid_channel(self, validator: PersonaValidator) -> None:
        yaml_content = textwrap.dedent("""\
            name: test
            version: "1.0.0"
            channels:
              - invalid-channel
        """)
        result = validator.validate_yaml(yaml_content)
        assert not result.valid
        assert any(e.code == INVALID_ENUM_VALUE for e in result.errors)

    def test_invalid_rule_level(self, validator: PersonaValidator) -> None:
        yaml_content = textwrap.dedent("""\
            name: test
            version: "1.0.0"
            rules:
              - id: r1
                type: existence
                level: critical
                tokens: [foo]
        """)
        result = validator.validate_yaml(yaml_content)
        assert not result.valid
        assert any(e.code == INVALID_ENUM_VALUE for e in result.errors)


class TestInvalidRange:
    """Test INVALID_RANGE error code."""

    def test_tone_above_one(self, validator: PersonaValidator) -> None:
        yaml_content = textwrap.dedent("""\
            name: test
            version: "1.0.0"
            tone:
              formality: 1.5
        """)
        result = validator.validate_yaml(yaml_content)
        assert not result.valid
        assert any(e.code == INVALID_RANGE for e in result.errors)

    def test_tone_below_zero(self, validator: PersonaValidator) -> None:
        yaml_content = textwrap.dedent("""\
            name: test
            version: "1.0.0"
            tone:
              warmth: -0.1
        """)
        result = validator.validate_yaml(yaml_content)
        assert not result.valid
        assert any(e.code == INVALID_RANGE for e in result.errors)


class TestInvalidSemver:
    """Test INVALID_SEMVER error code."""

    def test_not_semver(self, validator: PersonaValidator) -> None:
        result = validator.validate_yaml("name: test\nversion: v1.0")
        assert not result.valid
        assert any(e.code == INVALID_SEMVER for e in result.errors)

    def test_partial_semver(self, validator: PersonaValidator) -> None:
        result = validator.validate_yaml("name: test\nversion: '1.0'")
        assert not result.valid
        assert any(e.code == INVALID_SEMVER for e in result.errors)


class TestInvalidRegex:
    """Test INVALID_REGEX error code."""

    def test_bad_raw_regex(self, validator: PersonaValidator) -> None:
        yaml_content = textwrap.dedent("""\
            name: test
            version: "1.0.0"
            rules:
              - id: r1
                type: existence
                raw:
                  - "[invalid(regex"
        """)
        result = validator.validate_yaml(yaml_content)
        assert not result.valid
        assert any(e.code == INVALID_REGEX for e in result.errors)


class TestDuplicateRuleId:
    """Test DUPLICATE_RULE_ID error code."""

    def test_duplicate_ids(self, validator: PersonaValidator) -> None:
        yaml_content = textwrap.dedent("""\
            name: test
            version: "1.0.0"
            rules:
              - id: same-id
                type: existence
                tokens: [foo]
              - id: same-id
                type: existence
                tokens: [bar]
        """)
        result = validator.validate_yaml(yaml_content)
        assert not result.valid
        assert any(e.code == DUPLICATE_RULE_ID for e in result.errors)


class TestInvalidRuleType:
    """Test INVALID_RULE_TYPE error code."""

    def test_unknown_rule_type(self, validator: PersonaValidator) -> None:
        yaml_content = textwrap.dedent("""\
            name: test
            version: "1.0.0"
            rules:
              - id: r1
                type: nonexistent_type
                tokens: [foo]
        """)
        result = validator.validate_yaml(yaml_content)
        assert not result.valid
        assert any(e.code == INVALID_RULE_TYPE for e in result.errors)


class TestInvalidWeightsSum:
    """Test INVALID_WEIGHTS_SUM error code."""

    def test_weights_not_summing_to_one(
        self, validator: PersonaValidator,
    ) -> None:
        yaml_content = textwrap.dedent("""\
            name: test
            version: "1.0.0"
            health_score_weights:
              readability: 0.5
              naturalness: 0.5
              vocabulary: 0.5
              semantic_preservation: 0.0
              tone_compliance: 0.0
        """)
        result = validator.validate_yaml(yaml_content)
        assert not result.valid
        assert any(e.code == INVALID_WEIGHTS_SUM for e in result.errors)


class TestSecretDetected:
    """Test SECRET_DETECTED warning code."""

    def test_secret_field_name(self, validator: PersonaValidator) -> None:
        yaml_content = textwrap.dedent("""\
            name: test
            version: "1.0.0"
            password: my-secret-value
        """)
        result = validator.validate_yaml(yaml_content)
        assert any(w.code == SECRET_DETECTED for w in result.warnings)

    def test_aws_key_pattern(self, validator: PersonaValidator) -> None:
        yaml_content = textwrap.dedent("""\
            name: test
            version: "1.0.0"
            description: "Key is AKIAIOSFODNN7EXAMPLE"
        """)
        result = validator.validate_yaml(yaml_content)
        assert any(w.code == SECRET_DETECTED for w in result.warnings)

    def test_secrets_are_warnings_not_errors(
        self, validator: PersonaValidator,
    ) -> None:
        yaml_content = textwrap.dedent("""\
            name: test
            version: "1.0.0"
            api_key: some-key-value
        """)
        result = validator.validate_yaml(yaml_content)
        # Secrets produce warnings, not errors
        assert any(w.code == SECRET_DETECTED for w in result.warnings)


class TestExampleMismatch:
    """Test EXAMPLE_MISMATCH error code."""

    def test_valid_example_triggers_rule(
        self, validator: PersonaValidator,
    ) -> None:
        yaml_content = textwrap.dedent("""\
            name: test
            version: "1.0.0"
            rules:
              - id: no-foo
                type: existence
                tokens:
                  - foo
                examples:
                  valid:
                    - "this contains foo"
                  invalid:
                    - "this contains foo too"
        """)
        result = validator.validate_yaml(yaml_content)
        assert not result.valid
        assert any(e.code == EXAMPLE_MISMATCH for e in result.errors)

    def test_invalid_example_does_not_trigger(
        self, validator: PersonaValidator,
    ) -> None:
        yaml_content = textwrap.dedent("""\
            name: test
            version: "1.0.0"
            rules:
              - id: no-foo
                type: existence
                tokens:
                  - foo
                examples:
                  valid:
                    - "this is clean"
                  invalid:
                    - "this is also clean"
        """)
        result = validator.validate_yaml(yaml_content)
        assert not result.valid
        assert any(e.code == EXAMPLE_MISMATCH for e in result.errors)

    def test_correct_examples_pass(
        self, validator: PersonaValidator,
    ) -> None:
        yaml_content = textwrap.dedent("""\
            name: test
            version: "1.0.0"
            rules:
              - id: no-foo
                type: existence
                tokens:
                  - foo
                examples:
                  valid:
                    - "this is clean text"
                  invalid:
                    - "this contains foo"
        """)
        result = validator.validate_yaml(yaml_content)
        assert result.valid


class TestValidateDict:
    """Test validate_dict method directly."""

    def test_dict_validation(self, validator: PersonaValidator) -> None:
        data = {"name": "test", "version": "1.0.0"}
        result = validator.validate_dict(data)
        assert result.valid
