"""Tests for phraseturner.error_handler.

Validates the centralised error handling module: ``handle_tool_error``
for converting exceptions into structured responses, and
``tool_error_handler`` decorator for wrapping async tool functions.

Implements §6.1, §6.2, §6.3 of the design specification.
Requirements: FR-TOOL-01, FR-PIPELINE-01.
"""

from __future__ import annotations

import pytest

from phraseturner.error_handler import handle_tool_error, tool_error_handler
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
)

# ---------------------------------------------------------------------------
# handle_tool_error — PhraseturnerError subclasses
# ---------------------------------------------------------------------------


class TestHandleToolErrorKnown:
    """PhraseturnerError subclasses produce structured ToolError responses."""

    def test_text_too_long(self) -> None:
        exc = TextTooLongError("Text exceeds 8000 tokens", details={"token_count": 9000})
        result = handle_tool_error(exc)

        assert "error" in result
        assert result["error"]["code"] == "TEXT_TOO_LONG"
        assert "8000" in result["error"]["message"]
        assert result["error"]["details"] == {"token_count": 9000}
        assert "next_steps" in result
        assert isinstance(result["next_steps"], list)
        assert len(result["next_steps"]) >= 1

    def test_text_too_short(self) -> None:
        exc = TextTooShortError("Input is empty")
        result = handle_tool_error(exc)

        assert result["error"]["code"] == "TEXT_TOO_SHORT"
        assert result["error"]["details"] is None

    def test_persona_not_found(self) -> None:
        exc = PersonaNotFoundError(
            "No persona found matching 'foo'",
            details={"query": "foo"},
        )
        result = handle_tool_error(exc)

        assert result["error"]["code"] == "PERSONA_NOT_FOUND"
        assert result["error"]["details"] == {"query": "foo"}
        # NextStepsBuilder should suggest list_personas
        assert any("list_personas" in s for s in result["next_steps"])

    def test_persona_exists(self) -> None:
        exc = PersonaExistsError("Persona 'bar' already exists")
        result = handle_tool_error(exc)

        assert result["error"]["code"] == "PERSONA_EXISTS"

    def test_persona_validation_failed(self) -> None:
        exc = PersonaValidationError(
            "Schema validation failed",
            details={"errors": ["missing name"]},
        )
        result = handle_tool_error(exc)

        assert result["error"]["code"] == "PERSONA_VALIDATION_FAILED"
        assert result["error"]["details"] == {"errors": ["missing name"]}

    def test_invalid_focus_mode(self) -> None:
        exc = InvalidFocusModeError("Unknown focus mode 'xyz'")
        result = handle_tool_error(exc)

        assert result["error"]["code"] == "INVALID_FOCUS_MODE"

    def test_invalid_yaml(self) -> None:
        exc = InvalidYamlError("YAML parse error at line 5")
        result = handle_tool_error(exc)

        assert result["error"]["code"] == "INVALID_YAML"

    def test_model_load_failed(self) -> None:
        exc = ModelLoadError("spaCy model not found")
        result = handle_tool_error(exc)

        assert result["error"]["code"] == "MODEL_LOAD_FAILED"

    def test_base_phraseturner_error(self) -> None:
        exc = PhraseturnerError("generic error")
        result = handle_tool_error(exc)

        assert result["error"]["code"] == "PHRASETURNER_ERROR"


# ---------------------------------------------------------------------------
# handle_tool_error — unexpected exceptions
# ---------------------------------------------------------------------------


class TestHandleToolErrorUnexpected:
    """Unexpected exceptions produce sanitised INTERNAL_ERROR responses."""

    def test_runtime_error(self) -> None:
        exc = RuntimeError("something broke internally")
        result = handle_tool_error(exc)

        assert result["error"]["code"] == "INTERNAL_ERROR"
        assert result["error"]["message"] == "An unexpected error occurred"
        # Must NOT expose the internal error message
        assert "something broke" not in result["error"]["message"]
        assert result["error"]["details"] is None
        assert "next_steps" in result

    def test_value_error(self) -> None:
        exc = ValueError("bad value")
        result = handle_tool_error(exc)

        assert result["error"]["code"] == "INTERNAL_ERROR"
        assert "bad value" not in result["error"]["message"]

    def test_type_error(self) -> None:
        exc = TypeError("wrong type")
        result = handle_tool_error(exc)

        assert result["error"]["code"] == "INTERNAL_ERROR"

    def test_key_error(self) -> None:
        exc = KeyError("missing_key")
        result = handle_tool_error(exc)

        assert result["error"]["code"] == "INTERNAL_ERROR"


# ---------------------------------------------------------------------------
# tool_error_handler decorator
# ---------------------------------------------------------------------------


class TestToolErrorHandlerDecorator:
    """The @tool_error_handler decorator wraps async functions."""

    @pytest.mark.asyncio
    async def test_success_passthrough(self) -> None:
        """Successful return values pass through unchanged."""

        @tool_error_handler
        async def my_tool() -> dict[str, str]:
            return {"result": "ok"}

        result = await my_tool()
        assert result == {"result": "ok"}

    @pytest.mark.asyncio
    async def test_catches_phraseturner_error(self) -> None:
        """PhraseturnerError subclasses are caught and converted."""

        @tool_error_handler
        async def my_tool() -> dict[str, str]:
            raise TextTooLongError(
                "Too long",
                details={"token_count": 9999},
            )

        result = await my_tool()
        assert result["error"]["code"] == "TEXT_TOO_LONG"
        assert result["error"]["details"] == {"token_count": 9999}

    @pytest.mark.asyncio
    async def test_catches_unexpected_exception(self) -> None:
        """Unexpected exceptions are caught and sanitised."""

        @tool_error_handler
        async def my_tool() -> dict[str, str]:
            msg = "kaboom"
            raise RuntimeError(msg)

        result = await my_tool()
        assert result["error"]["code"] == "INTERNAL_ERROR"
        assert "kaboom" not in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_preserves_function_name(self) -> None:
        """functools.wraps preserves the original function metadata."""

        @tool_error_handler
        async def my_special_tool() -> dict[str, str]:
            return {"ok": "true"}

        assert my_special_tool.__name__ == "my_special_tool"

    @pytest.mark.asyncio
    async def test_passes_args_and_kwargs(self) -> None:
        """Arguments are forwarded correctly to the wrapped function."""

        @tool_error_handler
        async def my_tool(text: str, limit: int = 10) -> dict[str, object]:
            return {"text": text, "limit": limit}

        result = await my_tool("hello", limit=5)
        assert result == {"text": "hello", "limit": 5}

    @pytest.mark.asyncio
    async def test_persona_not_found_with_next_steps(self) -> None:
        """PersonaNotFoundError includes recovery next_steps."""

        @tool_error_handler
        async def my_tool() -> dict[str, str]:
            raise PersonaNotFoundError(
                "No persona 'xyz'",
                details={"query": "xyz"},
            )

        result = await my_tool()
        assert result["error"]["code"] == "PERSONA_NOT_FOUND"
        assert len(result["next_steps"]) >= 1


# ---------------------------------------------------------------------------
# Error response structure validation
# ---------------------------------------------------------------------------


class TestErrorResponseStructure:
    """All error responses have consistent structure."""

    def test_known_error_has_required_keys(self) -> None:
        exc = TextTooLongError("too long")
        result = handle_tool_error(exc)

        error = result["error"]
        assert "code" in error
        assert "message" in error
        assert "details" in error
        assert "next_steps" in result

    def test_unknown_error_has_required_keys(self) -> None:
        exc = RuntimeError("boom")
        result = handle_tool_error(exc)

        error = result["error"]
        assert "code" in error
        assert "message" in error
        assert "details" in error
        assert "next_steps" in result

    def test_error_code_is_string(self) -> None:
        exc = PersonaExistsError("exists")
        result = handle_tool_error(exc)
        assert isinstance(result["error"]["code"], str)

    def test_next_steps_is_list_of_strings(self) -> None:
        exc = TextTooShortError("empty")
        result = handle_tool_error(exc)
        assert isinstance(result["next_steps"], list)
        for step in result["next_steps"]:
            assert isinstance(step, str)
