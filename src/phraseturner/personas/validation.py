"""Persona validation with structured error codes.

Validates persona YAML content against the PersonaConfig schema using
Pydantic as the primary validation mechanism, then applies custom checks
for secrets, duplicate rules, regex patterns, and rule examples.

Implements section 3.6 of the design specification.
Requirements: FR-PERSONA-07, NFR-SEC-03, NFR-SEC-05.
"""

from __future__ import annotations

import re
from typing import Any

import structlog
import yaml

from phraseturner.models.persona import (
    ValidationError,
    ValidationResult,
)
from phraseturner.personas.rules import RuleEvaluator
from phraseturner.personas.schema import (
    Channel,
    PersonaConfig,
    RuleConfig,
    RuleLevel,
    RuleType,
)

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Error code constants -- FR-PERSONA-07 (AC-FR-PERSONA-07.2)
# ---------------------------------------------------------------------------
INVALID_YAML = "INVALID_YAML"
MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
INVALID_FIELD_TYPE = "INVALID_FIELD_TYPE"
INVALID_ENUM_VALUE = "INVALID_ENUM_VALUE"
INVALID_RANGE = "INVALID_RANGE"
INVALID_SEMVER = "INVALID_SEMVER"
INVALID_REGEX = "INVALID_REGEX"
DUPLICATE_RULE_ID = "DUPLICATE_RULE_ID"
INVALID_RULE_TYPE = "INVALID_RULE_TYPE"
EXAMPLE_MISMATCH = "EXAMPLE_MISMATCH"
INVALID_WEIGHTS_SUM = "INVALID_WEIGHTS_SUM"
SECRET_DETECTED = "SECRET_DETECTED"  # noqa: S105

# ---------------------------------------------------------------------------
# Secret detection patterns -- NFR-SEC-05
# ---------------------------------------------------------------------------
_SECRET_FIELD_NAMES = frozenset({
    "password", "secret", "token", "api_key", "private_key",
    "apikey", "api-key", "private-key", "secret_key", "secret-key",
    "access_key", "access-key",
})

_AWS_KEY_PATTERN = re.compile(r"AKIA[0-9A-Z]{16}")

# Semver pattern for pre-validation
_SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")

# Valid enum values for quick checking
_VALID_RULE_TYPES = frozenset(rt.value for rt in RuleType)
_VALID_RULE_LEVELS = frozenset(rl.value for rl in RuleLevel)
_VALID_CHANNELS = frozenset(ch.value for ch in Channel)

# Tone dimension names
_TONE_DIMENSIONS = frozenset({
    "formality", "confidence", "warmth",
    "directness", "energy", "verbosity",
})

_WEIGHTS_SUM_TOLERANCE = 0.001

# Rule types that are placeholders and cannot be example-validated
_PLACEHOLDER_RULE_TYPES = frozenset({
    RuleType.SCRIPT, RuleType.LLM_EVAL,
    RuleType.TONE, RuleType.BRAND_VOICE,
    RuleType.SEQUENCE,
})

# Pydantic type-string sets for error code mapping
_TYPE_ERROR_KINDS = frozenset({
    "string_type", "int_type", "float_type",
    "bool_type", "list_type", "dict_type",
})


class PersonaValidator:
    """Validate persona YAML content with structured error codes.

    Uses Pydantic's own validation as the primary mechanism, then adds
    custom checks for secrets, duplicate rule IDs, regex compilation,
    and rule example validation.

    Implements section 3.6, FR-PERSONA-07, NFR-SEC-03, NFR-SEC-05.
    """

    def __init__(self) -> None:
        self._evaluator = RuleEvaluator()

    def validate_yaml(self, yaml_content: str) -> ValidationResult:
        """Validate persona YAML content string.

        Main entry point. Parses YAML, then delegates to ``validate_dict``.

        Args:
            yaml_content: Raw YAML string to validate.

        Returns:
            ValidationResult with errors and warnings.
        """
        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as exc:
            return ValidationResult(
                valid=False,
                errors=[ValidationError(
                    path="",
                    code=INVALID_YAML,
                    message=f"YAML parsing failed: {exc}",
                )],
            )

        if not isinstance(data, dict):
            return ValidationResult(
                valid=False,
                errors=[ValidationError(
                    path="",
                    code=INVALID_YAML,
                    message=(
                        "YAML content must be a mapping, "
                        f"got {type(data).__name__}"
                    ),
                )],
            )

        return self.validate_dict(data)

    def validate_dict(self, data: dict[str, Any]) -> ValidationResult:
        """Validate a parsed persona dict.

        Runs validation in order: required fields, types, enums, ranges,
        semver, Pydantic model, custom checks (duplicates, regex, rule
        types, weights, secrets, examples).

        Args:
            data: Parsed YAML dict to validate.

        Returns:
            ValidationResult with all errors and warnings found.
        """
        errors: list[ValidationError] = []
        warnings: list[ValidationError] = []

        errors.extend(self._check_required_fields(data))
        errors.extend(self._check_field_types(data))
        errors.extend(self._check_enum_values(data))
        errors.extend(self._check_ranges(data))
        errors.extend(self._check_semver(data))
        errors.extend(self._check_pydantic(data))

        rules = data.get("rules", [])
        if isinstance(rules, list):
            errors.extend(self._check_duplicate_rules(rules))
            errors.extend(self._check_regex_patterns(rules))
            errors.extend(self._check_rule_types(rules))

        errors.extend(self._check_weights_sum(data))
        warnings.extend(self._check_secrets(data))

        # Example validation only when no structural errors
        if not errors and isinstance(rules, list):
            errors.extend(self._check_examples(rules))

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Pre-Pydantic structural checks
    # ------------------------------------------------------------------

    @staticmethod
    def _check_required_fields(
        data: dict[str, Any],
    ) -> list[ValidationError]:
        """Check that required top-level fields are present.

        Args:
            data: Parsed persona dict.

        Returns:
            Errors for each missing required field.
        """
        errors: list[ValidationError] = []
        for field in ("name", "version"):
            if field not in data:
                errors.append(ValidationError(
                    path=field,
                    code=MISSING_REQUIRED_FIELD,
                    message=f"Required field '{field}' is missing",
                ))
        return errors

    @staticmethod
    def _check_field_types(
        data: dict[str, Any],
    ) -> list[ValidationError]:
        """Validate types of top-level fields.

        Args:
            data: Parsed persona dict.

        Returns:
            Errors for fields with incorrect types.
        """
        errors: list[ValidationError] = []
        type_checks: list[tuple[str, type, str]] = [
            ("name", str, "string"),
            ("version", str, "string"),
            ("description", str, "string"),
            ("author", str, "string"),
            ("locale", str, "string"),
            ("channels", list, "list"),
            ("tags", list, "list"),
            ("tone", dict, "mapping"),
            ("rules", list, "list"),
        ]
        for field, expected, label in type_checks:
            value = data.get(field)
            if value is not None and not isinstance(value, expected):
                errors.append(ValidationError(
                    path=field,
                    code=INVALID_FIELD_TYPE,
                    message=(
                        f"Field '{field}' must be {label}, "
                        f"got {type(value).__name__}"
                    ),
                ))
        return errors

    @staticmethod
    def _check_enum_values(
        data: dict[str, Any],
    ) -> list[ValidationError]:
        """Validate enum fields against allowed values.

        Args:
            data: Parsed persona dict.

        Returns:
            Errors for invalid enum values.
        """
        errors: list[ValidationError] = []

        channels = data.get("channels", [])
        if isinstance(channels, list):
            for i, ch in enumerate(channels):
                if isinstance(ch, str) and ch not in _VALID_CHANNELS:
                    errors.append(ValidationError(
                        path=f"channels[{i}]",
                        code=INVALID_ENUM_VALUE,
                        message=(
                            f"Invalid channel '{ch}'. "
                            f"Valid: {sorted(_VALID_CHANNELS)}"
                        ),
                    ))

        rules = data.get("rules", [])
        if isinstance(rules, list):
            for i, rule in enumerate(rules):
                if not isinstance(rule, dict):
                    continue
                level = rule.get("level")
                if (
                    isinstance(level, str)
                    and level not in _VALID_RULE_LEVELS
                ):
                    errors.append(ValidationError(
                        path=f"rules[{i}].level",
                        code=INVALID_ENUM_VALUE,
                        message=(
                            f"Invalid rule level '{level}'. "
                            f"Valid: {sorted(_VALID_RULE_LEVELS)}"
                        ),
                    ))
        return errors

    @staticmethod
    def _check_ranges(
        data: dict[str, Any],
    ) -> list[ValidationError]:
        """Validate tone dimension values are in [0.0, 1.0] range.

        Args:
            data: Parsed persona dict.

        Returns:
            Errors for out-of-range tone dimensions.
        """
        errors: list[ValidationError] = []
        tone = data.get("tone")
        if not isinstance(tone, dict):
            return errors

        for dim in _TONE_DIMENSIONS:
            value = tone.get(dim)
            if (
                value is not None
                and isinstance(value, (int, float))
                and (value < 0.0 or value > 1.0)
            ):
                errors.append(ValidationError(
                    path=f"tone.{dim}",
                    code=INVALID_RANGE,
                    message=(
                        f"Tone dimension '{dim}' must be "
                        f"0.0-1.0, got {value}"
                    ),
                ))
        return errors

    @staticmethod
    def _check_semver(
        data: dict[str, Any],
    ) -> list[ValidationError]:
        """Validate version field matches semver pattern.

        Args:
            data: Parsed persona dict.

        Returns:
            Error if version is not valid semver.
        """
        version = data.get("version")
        if isinstance(version, str) and not _SEMVER_PATTERN.match(version):
            return [ValidationError(
                path="version",
                code=INVALID_SEMVER,
                message=(
                    f"Version '{version}' is not valid semver "
                    "(expected X.Y.Z)"
                ),
            )]
        return []

    # ------------------------------------------------------------------
    # Pydantic validation
    # ------------------------------------------------------------------

    @staticmethod
    def _check_pydantic(
        data: dict[str, Any],
    ) -> list[ValidationError]:
        """Attempt Pydantic model construction to catch schema violations.

        Maps Pydantic validation errors to structured error codes.

        Args:
            data: Parsed persona dict.

        Returns:
            Mapped validation errors from Pydantic.
        """
        try:
            PersonaConfig(**data)
        except Exception as exc:
            from pydantic import (  # noqa: PLC0415
                ValidationError as PydanticValidationError,
            )

            if not isinstance(exc, PydanticValidationError):
                return [ValidationError(
                    path="",
                    code=INVALID_FIELD_TYPE,
                    message=f"Schema validation failed: {exc}",
                )]

            return _map_pydantic_errors(exc)
        return []

    # ------------------------------------------------------------------
    # Custom checks
    # ------------------------------------------------------------------

    @staticmethod
    def _check_secrets(
        data: dict[str, Any],
    ) -> list[ValidationError]:
        """Scan for common secret patterns in all string values.

        Implements NFR-SEC-05.

        Args:
            data: Parsed persona dict.

        Returns:
            Warnings for detected secrets.
        """
        warnings: list[ValidationError] = []
        _scan_dict_for_secrets(data, "", warnings)
        return warnings

    @staticmethod
    def _check_duplicate_rules(
        rules: list[Any],
    ) -> list[ValidationError]:
        """Check for duplicate rule IDs.

        Args:
            rules: List of rule dicts from the persona.

        Returns:
            Errors for each duplicate rule ID.
        """
        errors: list[ValidationError] = []
        seen: dict[str, int] = {}

        for i, rule in enumerate(rules):
            if not isinstance(rule, dict):
                continue
            rule_id = rule.get("id")
            if not isinstance(rule_id, str):
                continue
            if rule_id in seen:
                errors.append(ValidationError(
                    path=f"rules[{i}].id",
                    code=DUPLICATE_RULE_ID,
                    message=(
                        f"Duplicate rule ID '{rule_id}' "
                        f"(first at rules[{seen[rule_id]}])"
                    ),
                ))
            else:
                seen[rule_id] = i
        return errors

    @staticmethod
    def _check_regex_patterns(
        rules: list[Any],
    ) -> list[ValidationError]:
        """Compile regex patterns in rules to detect invalid regexes.

        Args:
            rules: List of rule dicts from the persona.

        Returns:
            Errors for each invalid regex pattern.
        """
        errors: list[ValidationError] = []

        for i, rule in enumerate(rules):
            if not isinstance(rule, dict):
                continue

            raw_patterns = rule.get("raw", [])
            if isinstance(raw_patterns, list):
                for j, pattern in enumerate(raw_patterns):
                    if not isinstance(pattern, str):
                        continue
                    try:
                        re.compile(pattern)
                    except re.error as exc:
                        errors.append(ValidationError(
                            path=f"rules[{i}].raw[{j}]",
                            code=INVALID_REGEX,
                            message=f"Invalid regex '{pattern}': {exc}",
                        ))

            match_pattern = rule.get("match")
            if (
                isinstance(match_pattern, str)
                and not match_pattern.startswith("$")
            ):
                try:
                    re.compile(match_pattern)
                except re.error as exc:
                    errors.append(ValidationError(
                        path=f"rules[{i}].match",
                        code=INVALID_REGEX,
                        message=(
                            f"Invalid regex '{match_pattern}': {exc}"
                        ),
                    ))
        return errors

    @staticmethod
    def _check_rule_types(
        rules: list[Any],
    ) -> list[ValidationError]:
        """Check that rule types are valid.

        Args:
            rules: List of rule dicts from the persona.

        Returns:
            Errors for invalid rule types.
        """
        errors: list[ValidationError] = []
        for i, rule in enumerate(rules):
            if not isinstance(rule, dict):
                continue
            rule_type = rule.get("type")
            if (
                isinstance(rule_type, str)
                and rule_type not in _VALID_RULE_TYPES
            ):
                errors.append(ValidationError(
                    path=f"rules[{i}].type",
                    code=INVALID_RULE_TYPE,
                    message=(
                        f"Invalid rule type '{rule_type}'. "
                        f"Valid: {sorted(_VALID_RULE_TYPES)}"
                    ),
                ))
        return errors

    @staticmethod
    def _check_weights_sum(
        data: dict[str, Any],
    ) -> list[ValidationError]:
        """Check that health_score_weights sum to 1.0.

        Args:
            data: Parsed persona dict.

        Returns:
            Error if weights do not sum to 1.0.
        """
        weights = data.get("health_score_weights")
        if not isinstance(weights, dict):
            return []

        weight_fields = (
            "readability", "naturalness", "vocabulary",
            "semantic_preservation", "tone_compliance",
        )
        total = sum(
            weights.get(f, 0.0)
            for f in weight_fields
            if isinstance(weights.get(f), (int, float))
        )

        if abs(total - 1.0) > _WEIGHTS_SUM_TOLERANCE:
            return [ValidationError(
                path="health_score_weights",
                code=INVALID_WEIGHTS_SUM,
                message=f"Weights must sum to 1.0, got {total:.3f}",
            )]
        return []

    def _check_examples(
        self,
        rules: list[Any],
    ) -> list[ValidationError]:
        """Validate rule examples against the rule evaluator.

        Valid examples must not trigger the rule; invalid examples must
        trigger the rule. Implements AC-FR-PERSONA-07.3.

        Args:
            rules: List of rule dicts from the persona.

        Returns:
            Errors for example mismatches.
        """
        errors: list[ValidationError] = []

        for i, rule_data in enumerate(rules):
            if not isinstance(rule_data, dict):
                continue
            examples = rule_data.get("examples")
            if not isinstance(examples, dict):
                continue
            try:
                rule_config = RuleConfig(**rule_data)
            except Exception:
                logger.debug("rule_parse_skip", rule_index=i)
                continue
            if rule_config.type in _PLACEHOLDER_RULE_TYPES:
                continue

            errors.extend(
                self._validate_valid_examples(
                    rule_config, examples, i,
                ),
            )
            errors.extend(
                self._validate_invalid_examples(
                    rule_config, examples, i,
                ),
            )
        return errors

    def _validate_valid_examples(
        self,
        rule: RuleConfig,
        examples: dict[str, Any],
        rule_idx: int,
    ) -> list[ValidationError]:
        """Check that valid examples do NOT trigger the rule."""
        errors: list[ValidationError] = []
        valid_list = examples.get("valid", [])
        if not isinstance(valid_list, list):
            return errors
        for j, example in enumerate(valid_list):
            if not isinstance(example, str):
                continue
            matches = self._evaluator.evaluate(rule, example, [example])
            if matches:
                errors.append(ValidationError(
                    path=f"rules[{rule_idx}].examples.valid[{j}]",
                    code=EXAMPLE_MISMATCH,
                    message=(
                        f"Valid example triggered rule "
                        f"'{rule.id}': '{example}'"
                    ),
                ))
        return errors

    def _validate_invalid_examples(
        self,
        rule: RuleConfig,
        examples: dict[str, Any],
        rule_idx: int,
    ) -> list[ValidationError]:
        """Check that invalid examples DO trigger the rule."""
        errors: list[ValidationError] = []
        invalid_list = examples.get("invalid", [])
        if not isinstance(invalid_list, list):
            return errors
        for j, example in enumerate(invalid_list):
            if not isinstance(example, str):
                continue
            matches = self._evaluator.evaluate(rule, example, [example])
            if not matches:
                errors.append(ValidationError(
                    path=f"rules[{rule_idx}].examples.invalid[{j}]",
                    code=EXAMPLE_MISMATCH,
                    message=(
                        f"Invalid example did not trigger rule "
                        f"'{rule.id}': '{example}'"
                    ),
                ))
        return errors


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _scan_dict_for_secrets(
    data: Any,
    path: str,
    warnings: list[ValidationError],
) -> None:
    """Recursively scan a dict for secret patterns.

    Implements NFR-SEC-05.

    Args:
        data: Value to scan (dict, list, or scalar).
        path: JSON path prefix for error reporting.
        warnings: Accumulator for detected secret warnings.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            child_path = f"{path}.{key}" if path else key
            if (
                isinstance(key, str)
                and key.lower() in _SECRET_FIELD_NAMES
                and isinstance(value, str)
                and value
            ):
                warnings.append(ValidationError(
                    path=child_path,
                    code=SECRET_DETECTED,
                    message=f"Potential secret in field '{key}'",
                ))
            _scan_dict_for_secrets(value, child_path, warnings)
    elif isinstance(data, list):
        for i, item in enumerate(data):
            _scan_dict_for_secrets(item, f"{path}[{i}]", warnings)
    elif isinstance(data, str) and _AWS_KEY_PATTERN.search(data):
        warnings.append(ValidationError(
            path=path,
            code=SECRET_DETECTED,
            message="Potential AWS access key detected",
        ))


def _map_pydantic_errors(
    exc: Any,
) -> list[ValidationError]:
    """Map Pydantic ValidationError to structured error codes.

    Args:
        exc: A Pydantic ValidationError instance.

    Returns:
        List of mapped ValidationError objects.
    """
    errors: list[ValidationError] = []

    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", []))
        err_type = err.get("type", "")
        msg = err.get("msg", "Validation error")

        code = _pydantic_type_to_code(err_type, loc, msg)
        errors.append(ValidationError(path=loc, code=code, message=msg))

    return errors


# Direct mapping from Pydantic error types to phraseturner codes
_PYDANTIC_TYPE_MAP: dict[str, str] = {
    "missing": MISSING_REQUIRED_FIELD,
    "string_type": INVALID_FIELD_TYPE,
    "int_type": INVALID_FIELD_TYPE,
    "float_type": INVALID_FIELD_TYPE,
    "bool_type": INVALID_FIELD_TYPE,
    "list_type": INVALID_FIELD_TYPE,
    "dict_type": INVALID_FIELD_TYPE,
    "greater_than_equal": INVALID_RANGE,
    "less_than_equal": INVALID_RANGE,
    "literal_error": INVALID_ENUM_VALUE,
}


def _pydantic_type_to_code(
    err_type: str,
    loc: str,
    msg: str,
) -> str:
    """Map a Pydantic error type string to a phraseturner error code.

    Args:
        err_type: Pydantic error type (e.g. ``missing``, ``string_type``).
        loc: Field location path.
        msg: Error message.

    Returns:
        Corresponding phraseturner error code string.
    """
    direct = _PYDANTIC_TYPE_MAP.get(err_type)
    if direct is not None:
        return direct
    if "enum" in err_type:
        return INVALID_ENUM_VALUE
    if err_type == "string_pattern_mismatch":
        return INVALID_SEMVER if "version" in loc else INVALID_REGEX
    if err_type == "value_error" and "weight" in msg.lower():
        return INVALID_WEIGHTS_SUM
    return INVALID_FIELD_TYPE
