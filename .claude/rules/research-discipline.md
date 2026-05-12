# Research Discipline

Routing policy for research tool choices.

## Tier ladder (cheapest + most grounded first)

| Tier | Tool | Use for |
|------|------|---------|
| 0 | `basic-memory` MCP | Prior research on the topic (phraseturner project) — ALWAYS FIRST |
| 1 | `Grep` / `Glob` / `Read` | "Does the repo already answer this?" |
| 2 | `Context7` MCP | Library / framework API lookup (PydanticAI, Nova Act, LanceDB, spaCy) |
| 3 | `Exa` MCP | Semantic web search with filters |
| 4 | `WebFetch` | Specific known URL |
| 5 | `GitHub` MCP + `gh` CLI | Repo state, PRs, issues |
| 6 | `WebSearch` | Main session only — last resort |

## MANDATORY: prior-research check before Tier-2+

Before any Context7/Exa/WebFetch/WebSearch call:
1. `mcp__basic-memory__search_notes` for the topic
2. Grep relevant dirs in the phraseturner basic-memory project (phraseturner has extensive prior research)

If prior research exists, start there. Only call web tools to supplement or verify.

## WebSearch deprecated for sub-agents

SDK 422 bug on `server_tool_use` re-serialisation. Sub-agents must use `mcp__exa__web_search_exa` instead.

## Context7 library pins (phraseturner relevant)

- PydanticAI: `/pydantic/pydantic-ai`
- Pydantic v2: `/pydantic/pydantic`
- Hypothesis: `/hypothesisworks/hypothesis`
- spaCy: `/explosion/spacy`
- LanceDB: `/lancedb/lancedb`
- RenderCV: `/rendercv/rendercv`
- Nova Act: unknown — use Exa to find

## Circuit breakers

Stop searching when:
- A project decision (in `docs/decisions/` or basic-memory) answers the question.
- Context7 returned ≥3 relevant examples.
- Two independent sources agree.
- 3 Exa calls on the same topic (budget gate).

## Memory write-back

Durable conclusions WRITE to basic-memory after research. Templates in `tool-selection.md`.
