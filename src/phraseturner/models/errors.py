"""Error response data models for phraseturner.

Implements §2.5 and §6.2 of the design specification.
Structured error models returned by MCP tools and the analysis pipeline.

Implements FR-TOOL-01, FR-TOOL-03, FR-TOOL-04.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolError(BaseModel):
    """Structured error response for all MCP tools.

    Implements §2.5.

    Attributes:
        code: Machine-readable error code (e.g. ``TEXT_TOO_LONG``).
        message: Human-readable error description.
        details: Optional additional context for debugging.
    """

    code: str = Field(description="Machine-readable error code.")
    message: str = Field(description="Human-readable error description.")
    details: dict[str, Any] | None = Field(
        default=None, description="Additional context."
    )


class AnalysisError(BaseModel):
    """Structured error with optional partial results from the pipeline.

    Returned when the analysis pipeline encounters an error but has
    partial results from completed stages. Implements §6.2.

    Attributes:
        code: Machine-readable error code.
        message: Human-readable error description.
        details: Optional additional context for debugging.
        partial_results: Partial analysis results from stages that
            completed before the error. At runtime this is an
            ``AnalysisResult`` instance; typed as ``Any`` to avoid
            circular imports.
    """

    code: str
    message: str
    details: dict[str, Any] | None = None
    partial_results: Any = None
