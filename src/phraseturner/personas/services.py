"""Persona service functions for create and validate operations.

Implements the business logic behind the ``create_persona`` and
``validate_persona`` MCP tools.

Requirements: FR-TOOL-04, FR-TOOL-05, FR-PERSONA-09.
Design: §2.4, §3.6.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
import yaml

from phraseturner.exceptions import PersonaExistsError, PersonaValidationError
from phraseturner.models.persona import PersonaCreateResult, ValidationResult
from phraseturner.personas.schema import PersonaConfig
from phraseturner.personas.validation import PersonaValidator

if TYPE_CHECKING:
    from phraseturner.config import ServerConfig
    from phraseturner.personas.index import PersonaIndex

logger = structlog.get_logger()

# Module-level validator instance (stateless, safe to reuse).
_validator = PersonaValidator()

# Regex for safe persona names (filesystem-safe, no path traversal).
_VALID_PERSONA_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _sanitize_persona_name(name: str) -> str:
    """Validate persona name is safe for filesystem use.

    Prevents path traversal attacks by enforcing a strict character set.
    Only lowercase alphanumeric characters and hyphens are allowed.

    Args:
        name: The persona name to validate.

    Returns:
        The validated name (unchanged if valid).

    Raises:
        PersonaValidationError: If the name contains unsafe characters.
    """
    if not _VALID_PERSONA_NAME.match(name):
        raise PersonaValidationError(
            f"Invalid persona name '{name}'. Must match ^[a-z0-9][a-z0-9-]*$",
            details={"name": name, "pattern": "^[a-z0-9][a-z0-9-]*$"},
        )
    return name

# Default user-tier persona directory.
_DEFAULT_USER_DIR = Path("~/.config/phraseturner/personas")


def _resolve_user_directory(config: ServerConfig) -> Path:
    """Determine the user-tier persona directory.

    Uses ``config.personas_dir`` when set, otherwise falls back to
    ``~/.config/phraseturner/personas/``.

    Implements AC-FR-PERSONA-09.1.

    Args:
        config: Server configuration.

    Returns:
        Resolved absolute path to the user persona directory.
    """
    if config.personas_dir is not None:
        return config.personas_dir
    return _DEFAULT_USER_DIR.expanduser()


async def create_persona(
    yaml_content: str,
    config: ServerConfig,
    persona_index: PersonaIndex,
) -> PersonaCreateResult:
    """Create a new persona from YAML content.

    Validates the YAML, checks for duplicates in the user directory,
    writes the file, and registers the persona in the index.

    Implements FR-TOOL-04 (AC-FR-TOOL-04.1, AC-FR-TOOL-04.2,
    AC-FR-TOOL-04.3), FR-PERSONA-09 (AC-FR-PERSONA-09.2).

    Args:
        yaml_content: Raw YAML string defining the persona.
        config: Server configuration for directory resolution.
        persona_index: Live persona index to register the new persona.

    Returns:
        PersonaCreateResult with name, file path, and validation status.

    Raises:
        PersonaValidationError: If the YAML fails schema validation
            (AC-FR-TOOL-04.2).
        PersonaExistsError: If a persona with the same name already
            exists in the user directory (AC-FR-TOOL-04.3).
    """
    # Step 1: Validate YAML content — AC-FR-TOOL-04.1
    validation = _validator.validate_yaml(yaml_content)
    if not validation.valid:
        logger.warning(
            "persona_create_validation_failed",
            error_count=len(validation.errors),
        )
        raise PersonaValidationError(
            "Persona YAML failed validation",
            details={
                "errors": [e.model_dump() for e in validation.errors],
            },
        )

    # Step 2: Parse YAML to extract persona name
    data = yaml.safe_load(yaml_content)
    persona_config = PersonaConfig.model_validate(data)
    name = persona_config.name

    # Step 2b: Sanitize name to prevent path traversal — C7
    _sanitize_persona_name(name)

    # Step 3: Check for duplicate in user directory — AC-FR-TOOL-04.3
    user_dir = _resolve_user_directory(config)
    target_path = user_dir / f"{name}.yaml"

    if target_path.exists():
        raise PersonaExistsError(
            f"Persona '{name}' already exists in user directory",
            details={"name": name, "path": str(target_path)},
        )

    # Step 4: Create user directory if missing — AC-FR-PERSONA-09.2
    user_dir.mkdir(parents=True, exist_ok=True)

    # Step 5: Write YAML file to user directory
    target_path.write_text(yaml_content, encoding="utf-8")
    logger.info(
        "persona_created",
        name=name,
        path=str(target_path),
    )

    # Step 6: Register in the persona index
    persona_index.add(name, persona_config, tier="user")

    return PersonaCreateResult(
        name=name,
        file_path=str(target_path),
        validation=validation,
    )


async def validate_persona(yaml_content: str) -> ValidationResult:
    """Validate persona YAML content without saving.

    Pure validation with no side effects — does not write files or
    modify the persona index.

    Implements FR-TOOL-05 (AC-FR-TOOL-05.1, AC-FR-TOOL-05.2,
    AC-FR-TOOL-05.3).

    Args:
        yaml_content: Raw YAML string to validate.

    Returns:
        ValidationResult with valid flag, errors, and warnings.
    """
    return _validator.validate_yaml(yaml_content)
