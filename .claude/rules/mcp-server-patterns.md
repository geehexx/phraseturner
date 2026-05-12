---
description: "FastMCP tool authoring patterns for phraseturner. Every MCP tool MUST accept typed Pydantic input + return typed Pydantic output + include an `explanation` field for Kiro IDE + Claude Code compatibility. Always loaded."
alwaysApply: true
---

# MCP Server Patterns (FastMCP 3.2+)

## Every tool MUST

1. Accept a typed `BaseModel` input (never `dict[str, Any]`)
2. Return a typed `BaseModel` subclass (not a raw dict)
3. Include an `explanation: str` field — Kiro IDE renders this inline; Claude Code surfaces it in tool-result blocks
4. Have a docstring with 6 sections: PURPOSE, Use for, Constraints, Side effects, Follow-up, Errors
5. Be registered with `_ANN_RO_IDEM` or `_ANN_WRITE` annotations to surface read-only vs write semantics

## Example

```python
from pydantic import BaseModel, Field
from fastmcp import FastMCP

mcp = FastMCP("phraseturner")

class ScoreReadabilityInput(BaseModel):
    text: str = Field(..., description="Text to score")
    persona: str | None = Field(None, description="Optional persona override")

class ScoreReadabilityOutput(BaseModel):
    flesch_score: float
    grade_level: float
    explanation: str  # REQUIRED for Kiro/Claude Code
    next_steps: list[str] = Field(default_factory=list)

@mcp.tool(annotations=_ANN_RO_IDEM)
async def score_readability(input: ScoreReadabilityInput) -> ScoreReadabilityOutput:
    """Score readability via Flesch reading ease.

    PURPOSE: return a deterministic readability metric for a given text.
    Use for: pre-flight checks before publishing user-facing content.
    Constraints: input ≤ 10k chars; non-English text returns None.
    Side effects: none — pure function.
    Follow-up: if grade_level > 12, suggest simplification tools.
    Errors: raises McpError if text is empty or non-string.
    """
    ...
```

## Anti-patterns

- ❌ `@mcp.tool` without type annotations
- ❌ returning raw strings or dicts (FastMCP's encoder can't handle datetimes/UUIDs safely)
- ❌ silently catching exceptions — always raise `McpError` with actionable message
- ❌ hardcoding persona names in tool logic (personas are config)
- ❌ any non-deterministic scoring (LLM calls in scoring path) — scoring must be reproducible
