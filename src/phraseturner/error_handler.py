"""Centralised error handling for MCP tool functions.

Provides ``handle_tool_error`` for converting exceptions into structured
error response dicts, and ``tool_error_handler`` as a decorator that
wraps async tool functions with try/except for both
``PhraseturnerError`` subclasses and unexpected exceptions.

Implements §6.1, §6.2, §6.3 of the design specification.
Requirements: FR-TOOL-01, FR-PIPELINE-01.
"""

from __future__ import annotations

import functools
from typing import Any

import structlog

from phraseturner.exceptions import PhraseturnerError
from phraseturner.models.errors import ToolError
from phraseturner.next_steps import NextStepsBuilder

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

_next_steps = NextStepsBuilder()


def handle_tool_error(exc: Exception) -> dict[str, Any]:
    """Convert an exception into a structured tool error response.

    If *exc* is a ``PhraseturnerError`` subclass the response includes
    the domain-specific error code, the original message, any attached
    details, and contextual recovery suggestions via ``NextStepsBuilder``.

    For unexpected exceptions the response uses ``INTERNAL_ERROR`` with
    a sanitised message that never exposes stack traces or internal
    details.  The full traceback is logged via structlog for debugging.

    Implements §6.1, §6.2.

    Args:
        exc: The caught exception — either a ``PhraseturnerError``
            subclass or an unexpected ``Exception``.

    Returns:
        Dict with ``error`` key (code, message, details) and
        ``next_steps`` list for recovery guidance.
    """
    if isinstance(exc, PhraseturnerError):
        return {
            "error": ToolError(
                code=exc.code,
                message=str(exc),
                details=exc.details,
            ).model_dump(),
            "next_steps": _next_steps.for_error(exc.code),
        }

    # Unexpected exception — sanitise and log.
    logger.exception("tool_internal_error", error=str(exc))
    return {
        "error": ToolError(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred",
            details=None,
        ).model_dump(),
        "next_steps": _next_steps.for_error("INTERNAL_ERROR"),
    }


def tool_error_handler(func: Any) -> Any:
    """Decorator wrapping async tool functions with error handling.

    Catches ``PhraseturnerError`` subclasses and unexpected exceptions,
    converting them into structured error response dicts via
    ``handle_tool_error``.

    Implements §6.1, §6.2.

    Args:
        func: An async tool function to wrap.

    Returns:
        Wrapped async function with try/except error handling.
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await func(*args, **kwargs)
        except PhraseturnerError as exc:
            return handle_tool_error(exc)
        except Exception as exc:
            return handle_tool_error(exc)

    return wrapper
