"""Tests for phraseturner.exceptions — hierarchy, error codes, attributes.

Validates: NFR-QUAL-04.
"""

from __future__ import annotations

from phraseturner.exceptions import (
    InvalidFocusModeError,
    InvalidYamlError,
    ModelLoadError,
    PersonaExistsError,
    PersonaNotFoundError,
    PersonaValidationError,
    PhraseturnerError,
    TextTooLongError,
    TextTooShortError,
    TextValidationError,
)


class TestExceptionHierarchy:
    """All exceptions inherit from PhraseturnerError."""

    def test_text_validation_is_phraseturner_error(self) -> None:
        assert issubclass(TextValidationError, PhraseturnerError)

    def test_text_too_long_is_text_validation(self) -> None:
        assert issubclass(TextTooLongError, TextValidationError)

    def test_text_too_short_is_text_validation(self) -> None:
        assert issubclass(TextTooShortError, TextValidationError)

    def test_persona_not_found_is_phraseturner_error(self) -> None:
        assert issubclass(PersonaNotFoundError, PhraseturnerError)

    def test_persona_exists_is_phraseturner_error(self) -> None:
        assert issubclass(PersonaExistsError, PhraseturnerError)

    def test_persona_validation_is_phraseturner_error(self) -> None:
        assert issubclass(PersonaValidationError, PhraseturnerError)

    def test_invalid_yaml_is_phraseturner_error(self) -> None:
        assert issubclass(InvalidYamlError, PhraseturnerError)

    def test_invalid_focus_mode_is_phraseturner_error(self) -> None:
        assert issubclass(InvalidFocusModeError, PhraseturnerError)

    def test_model_load_is_phraseturner_error(self) -> None:
        assert issubclass(ModelLoadError, PhraseturnerError)


class TestErrorCodes:
    """Each exception has the correct error code class attribute."""

    def test_base_code(self) -> None:
        assert PhraseturnerError.code == "PHRASETURNER_ERROR"

    def test_text_validation_code(self) -> None:
        assert TextValidationError.code == "TEXT_VALIDATION_ERROR"

    def test_text_too_long_code(self) -> None:
        assert TextTooLongError.code == "TEXT_TOO_LONG"

    def test_text_too_short_code(self) -> None:
        assert TextTooShortError.code == "TEXT_TOO_SHORT"

    def test_invalid_focus_mode_code(self) -> None:
        assert InvalidFocusModeError.code == "INVALID_FOCUS_MODE"

    def test_persona_not_found_code(self) -> None:
        assert PersonaNotFoundError.code == "PERSONA_NOT_FOUND"

    def test_persona_exists_code(self) -> None:
        assert PersonaExistsError.code == "PERSONA_EXISTS"

    def test_persona_validation_code(self) -> None:
        assert PersonaValidationError.code == "PERSONA_VALIDATION_FAILED"

    def test_invalid_yaml_code(self) -> None:
        assert InvalidYamlError.code == "INVALID_YAML"

    def test_model_load_code(self) -> None:
        assert ModelLoadError.code == "MODEL_LOAD_FAILED"


class TestExceptionAttributes:
    """Exception instances store message and details correctly."""

    def test_message_stored(self) -> None:
        exc = PhraseturnerError("test message")
        assert exc.message == "test message"
        assert str(exc) == "test message"

    def test_details_default_none(self) -> None:
        exc = PhraseturnerError("msg")
        assert exc.details is None

    def test_details_stored(self) -> None:
        exc = TextTooLongError("too long", details={"token_count": 9000})
        assert exc.details == {"token_count": 9000}

    def test_code_on_instance(self) -> None:
        exc = PersonaNotFoundError("not found")
        assert exc.code == "PERSONA_NOT_FOUND"

    def test_catchable_as_base(self) -> None:
        exc = TextTooLongError("too long")
        assert isinstance(exc, PhraseturnerError)
        assert isinstance(exc, Exception)
