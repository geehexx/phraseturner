# Phraseturner Development Context

## CRITICAL RULES

- **Personas are config, not code** — define in `data/personas/*.yaml`, never hardcode logic branches on persona name
- **Scoring is deterministic** — no LLM in the scoring path. textstat / vaderSentiment / lexicalrichness / is-it-slop return numeric scores; LLM only in optional user-facing rewrite helpers
- **FastMCP tool signatures MUST use Pydantic BaseModel return types** — Kiro IDE + Claude Code both require structured tool responses
- **NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE** — Iron Law
- **British English for all user-facing text** — `colour`, `organisation`, `analyse`. Code + tests in en_US per Python convention
- Empty turns (hook responses, system reminders, task notifications) are NOT user messages — see `.claude/rules/empty-turn-attribution.md`
- Never bypass pre-commit hooks (`--no-verify`, `SKIP=` are prohibited) — fix the root cause
- No AI attribution in commits, PRs, or user-facing docs

## Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Runtime | Python 3.12+ | `.python-version` pins it |
| Package manager | uv | NEVER pip |
| Server | FastMCP 3.2+ | MCP protocol — tool discovery + structured JSON replies |
| NLP | spaCy `en_core_web_sm`, textstat, vaderSentiment, lexicalrichness | readability + sentiment + lexical diversity |
| Embeddings | ONNX Runtime + fastembed | local semantic similarity |
| Slop detection | `is-it-slop` 0.5+ | AI-generated text heuristics |
| Personas | YAML config (`data/personas/*.yaml`) + pydantic-settings | hot-reload via watchfiles |
| Testing | pytest + Hypothesis | unit / integration / properties / calibration marks |
| Lint/Format | ruff | NEVER black/flake8/isort |
| Type check | mypy strict | |
| Logging | structlog | NEVER stdlib logging |

## Architecture

```
phraseturner/
├── src/phraseturner/
│   ├── server.py          # FastMCP app + tool registrations
│   ├── tools/             # MCP tool functions (one per scoring category)
│   ├── personas/          # persona loading + validation
│   ├── scoring/           # textstat / vader / lexicalrichness / slop adapters
│   ├── embeddings/        # ONNX singleton for semantic similarity
│   └── config.py          # pydantic-settings for env config
├── data/
│   └── personas/          # YAML persona definitions
├── tests/
│   ├── unit/              # mirrors src/phraseturner/
│   ├── integration/       # FastMCP in-memory client tests
│   ├── properties/        # Hypothesis property tests
│   └── calibration/       # scoring-rubric regression fixtures
└── docs/
```

**Tool pattern** (for every MCP tool):
- Accept typed pydantic input model
- Return typed pydantic output model
- Include an `explanation` field for Kiro IDE / Claude Code compatibility
- Never swallow errors silently — raise `McpError` with actionable message

## Tool & Shell Patterns

```bash
# Python — always uv
uv run pytest                    # All tests
uv run pytest -m unit            # unit tests only
uv run ruff check src/ tests/    # Lint
uv run mypy --strict src/        # Type check

# Running the MCP server (stdio)
uv run phraseturner

# Testing with FastMCP in-memory client
uv run pytest tests/integration/test_pipeline.py
```

## Known Gotchas

### Persona hot-reload — watchfiles race
`data/personas/*.yaml` is watched at runtime. If you edit + save inside the same ~100 ms, watchfiles may coalesce events and skip reload. Always `touch data/personas/` to force a reload event during dev.

### textstat + Unicode
`textstat.flesch_reading_ease()` silently returns 0 on text containing only non-ASCII characters. Guard with `if not any(c.isascii() for c in text): return None`.

### FastMCP tool response types
Return `BaseModel` subclasses, not raw dicts. FastMCP's JSON encoder handles Pydantic but raises TypeError on complex nested dicts with datetimes/UUIDs.

### ALLOW_MODEL_REQUESTS in tests
If any tool path invokes a PydanticAI agent (there aren't any today, but if added): set `pydantic_ai.ALLOW_MODEL_REQUESTS = False` in `tests/conftest.py` and use `TestModel` via `Agent.override()`.

## Conventions

- Python: snake_case modules, PascalCase classes, absolute imports from `phraseturner`
- Python 3.12+: `type PersonaName = str`, `itertools.batched()`, `|` union syntax
- Tests: `test_*.py`, `@settings(deadline=None)` for Hypothesis
- Content language: British English for all user-facing text (docs, tool descriptions, personas)
- Logging: structlog with bound context (`logger.bind(persona=..., tool=...)`)

## Memory

Basic-memory project `phraseturner` — path declared in `~/.basic-memory/config.json` (not tracked in-repo). Searchable via `mcp__basic-memory__search_notes`. Durable research + decisions go there; active plans in `docs/plans/`.
