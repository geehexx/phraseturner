"""phraseturner exception hierarchy.

Structured exceptions with machine-readable error codes for all tool error
responses.  Every public exception carries a ``code`` class attribute that
maps directly to the error catalog in §6.1 of the design specification.

Implements §6.4 (Exception Hierarchy).
Requirements: FR-TOOL-01, FR-TOOL-03, FR-TOOL-04.
"""

from __future__ import annotations


class PhraseturnerError(Exception):
    """Base exception for all phraseturner errors.

    Attributes:
        code: Machine-readable error code (set as a class attribute on
            each subclass).
        message: Human-readable description of the error.
        details: Optional mapping of additional context for debugging.
    """

    code: str = "PHRASETURNER_ERROR"

    def __init__(
        self,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


# ---------------------------------------------------------------------------
# Input validation errors
# ---------------------------------------------------------------------------


class TextValidationError(PhraseturnerError):
    """Base for text-input validation failures."""

    code: str = "TEXT_VALIDATION_ERROR"


class TextTooLongError(TextValidationError):
    """Input text exceeds the 8 000-token limit. Implements AC-FR-TOOL-01.7."""

    code: str = "TEXT_TOO_LONG"


class TextTooShortError(TextValidationError):
    """Input text is empty or whitespace-only. Implements §6.1 TEXT_TOO_SHORT."""

    code: str = "TEXT_TOO_SHORT"


class InvalidFocusModeError(PhraseturnerError):
    """An unrecognised focus mode was supplied. Implements §6.1 INVALID_FOCUS_MODE."""

    code: str = "INVALID_FOCUS_MODE"


# ---------------------------------------------------------------------------
# Persona errors
# ---------------------------------------------------------------------------


class PersonaNotFoundError(PhraseturnerError):
    """No persona matched the given name or query. Implements AC-FR-TOOL-03.3."""

    code: str = "PERSONA_NOT_FOUND"


class PersonaExistsError(PhraseturnerError):
    """A persona with the same name already exists. Implements AC-FR-TOOL-04.3."""

    code: str = "PERSONA_EXISTS"


class PersonaValidationError(PhraseturnerError):
    """Persona YAML failed schema validation. Implements AC-FR-TOOL-04.2."""

    code: str = "PERSONA_VALIDATION_FAILED"


class InvalidYamlError(PhraseturnerError):
    """YAML content could not be parsed. Implements §6.1 INVALID_YAML."""

    code: str = "INVALID_YAML"


# ---------------------------------------------------------------------------
# System / model errors
# ---------------------------------------------------------------------------


class ModelLoadError(PhraseturnerError):
    """A required model failed to load at startup. Implements §6.1 MODEL_LOAD_FAILED."""

    code: str = "MODEL_LOAD_FAILED"
