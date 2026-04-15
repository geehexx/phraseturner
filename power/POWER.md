---
name: phraseturner
description: Text analysis MCP server with configurable personas for readability, naturalness, tone, and AI detection
keywords: text, analysis, readability, naturalness, tone, persona, writing, quality, score, grade, humanize, review, style
---

# phraseturner

Text analysis MCP server that provides structured feedback on writing quality. Analyses text against configurable personas and returns readability scores, naturalness metrics, vocabulary analysis, tone assessment, AI detection signals, and per-sentence deep analysis via FLAN-T5.

phraseturner **never rewrites text** — it analyses and returns structured feedback that the calling LLM uses to make its own rewriting decisions.

## Installation

```bash
# Run directly (no install needed)
uvx phraseturner

# Or install permanently
uv pip install phraseturner
```

## Tools

### `analyze` — Full Pipeline Analysis

Comprehensive text quality analysis against an optional persona. Runs the full 6-stage pipeline including FLAN-T5 deep analysis.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `text` | string | Yes | — | Text to analyse (1–8000 tokens) |
| `persona` | string | No | null | Persona name or semantic query |
| `focus` | string | No | "full" | Focus mode: full, readability, naturalness, persona_compliance |
| `include_suggestions` | boolean | No | false | Include up to 5 actionable hints |
| `original_text` | string | No | null | Original text for semantic preservation scoring |
| `response_format` | string | No | "detailed" | "concise" or "detailed" |

Returns: health score (0–100, letter grade), per-sentence analysis, persona alignment, flags, suggestions, and next steps.

Latency: ≤500ms for ≤5 sentences.

### `score` — Quick Health Score

Fast health score without FLAN-T5 deep analysis. Use for rapid quality checks during iterative rewriting.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `text` | string | Yes | — | Text to score |
| `persona` | string | No | null | Persona name or semantic query |

Returns: composite score (0–100), letter grade, per-dimension breakdown, and next steps.

Latency: ≤50ms for ≤5 sentences.

### `compare` — Compare Original vs Rewrite

Compare an original text with a rewritten version to assess whether the rewrite preserved meaning and improved quality.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `original` | string | Yes | — | Original text |
| `rewritten` | string | Yes | — | Rewritten text |
| `persona` | string | No | null | Persona for compliance comparison |
| `response_format` | string | No | "detailed" | "concise" or "detailed" |

Returns: semantic similarity, per-dimension deltas, overall improvement score, sentence alignment, and next steps.

Latency: ≤800ms.

### `list_personas` — List Available Personas

List all available personas with optional semantic search or tag filtering.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | No | null | Semantic search query |
| `tags` | list[string] | No | null | Filter by tags (all must match) |

Returns: list of persona summaries with name, description, tags, tier, and version.

### `get_persona` — Get Persona Detail

Retrieve the full definition of a specific persona by exact name or semantic query.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `name_or_query` | string | Yes | — | Persona name or semantic query |

Returns: full persona definition including tone dimensions, brand voice, vocabulary, and rules.

### `create_persona` — Create Persona

Create a new persona by submitting YAML content. Validates against the persona schema and writes to the user persona directory.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `yaml_content` | string | Yes | — | Valid persona YAML content |

Returns: file path and validation status.

### `validate_persona` — Validate Persona

Validate persona YAML content without saving. Use to check for errors before committing.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `yaml_content` | string | Yes | — | Persona YAML content to validate |

Returns: valid (boolean), errors list, warnings list.

## When to Use Which Tool

| Goal | Tool | Why |
|------|------|-----|
| Full quality assessment | `analyze` | Complete pipeline with T5 deep analysis |
| Quick quality check | `score` | Fast feedback without T5 overhead |
| Assess a rewrite | `compare` | Measures improvement and meaning preservation |
| Find a persona | `list_personas` | Discover available personas by query or tags |
| Understand a persona | `get_persona` | See full tone targets and rules |
| Create custom rules | `create_persona` | Define project-specific analysis rules |
| Check YAML before saving | `validate_persona` | Catch schema errors early |

## Recommended Personas

| Context | Persona | Key Focus |
|---------|---------|-----------|
| Slack messages | `slack-casual` | Low formality, high warmth, concise |
| Pull request reviews | `pr-review` | Direct, technical, constructive |
| Wiki/docs | `confluence-docs` | Clear, structured, moderate formality |
| JIRA tickets | `jira-ticket` | Concise, actionable, specific |
| Business email | `email-professional` | Professional tone, moderate formality |
| Blog content | `blog-post` | Engaging, accessible, varied structure |
| Technical documentation | `technical-docs` | Precise, formal, comprehensive |
| Executive summaries | `executive-summary` | High-level, confident, concise |
| Detect internal tooling leaks | `internal-references` | Flags memory URIs, agent paths, internal tool names |

## Common Workflow

```
analyse → identify issues → rewrite → compare → score final version
```

1. Call `analyze` with a persona to get detailed feedback
2. Use the flags and suggestions to guide rewriting
3. Call `compare` with original and rewritten text to measure improvement
4. Call `score` on the final version to confirm quality

## Full API Documentation

See the [phraseturner docs](https://github.com/geehexx/phraseturner) for complete API reference, persona authoring guide, and configuration options.
