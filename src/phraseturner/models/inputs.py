"""Input schemas for phraseturner MCP tools.

Implements §2.1 of the design specification.

Implements FR-TOOL-01.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from phraseturner.models.analysis import ResponseFormat


class FocusMode(StrEnum):
    """Analysis focus modes restricting which dimensions are evaluated.

    Implements AC-FR-TOOL-01.3.
    """

    FULL = "full"
    READABILITY = "readability"
    NATURALNESS = "naturalness"
    PERSONA_COMPLIANCE = "persona_compliance"


class AnalyzeInput(BaseModel):
    """Input schema for the ``analyze`` tool.

    Implements FR-TOOL-01, FR-TOOL-09.

    Attributes:
        text: Text to analyse (1-8000 tokens).
        persona: Persona name or semantic query for persona resolution.
        focus: Restrict analysis to a specific dimension.
        include_suggestions: Include up to 5 actionable analysis hints.
        original_text: Original text for semantic preservation scoring.
        response_format: Response verbosity (concise omits per-sentence breakdowns).
    """

    text: str = Field(
        ...,
        min_length=1,
        description="Text to analyse (1-8000 tokens).",
    )
    persona: str | None = Field(
        default=None,
        description="Persona name or semantic query.",
    )
    focus: FocusMode = Field(
        default=FocusMode.FULL,
        description="Restrict analysis dimension.",
    )
    include_suggestions: bool = Field(
        default=False,
        description="Include up to 5 hints.",
    )
    original_text: str | None = Field(
        default=None,
        description="Original text for semantic preservation.",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.DETAILED,
        description="Response verbosity.",
    )
