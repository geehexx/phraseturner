# phraseturner

Text analysis MCP server with configurable personas for readability, naturalness, tone, and AI detection.

phraseturner analyses text and returns structured feedback — readability scores, naturalness metrics, vocabulary analysis, tone assessment, AI detection signals, and per-sentence deep analysis via FLAN-T5. It **never rewrites text**; it provides feedback that a calling LLM uses to make its own rewriting decisions.

## Key Features

- **7 MCP tools** — `analyze`, `score`, `compare`, `list_personas`, `get_persona`, `create_persona`, `validate_persona`
- **Configurable personas** — Vale-compatible YAML rules extended with tone dimensions, brand voice, and LLM-evaluated rules
- **6-stage analysis pipeline** — classical NLP (spaCy, textstat, VADER), AI detection (is-it-slop), and FLAN-T5 deep analysis
- **Composite health score** — 0–100 score across 5 dimensions with letter grades (A–F)
- **Graceful degradation** — 5-tier operating model; works with just textstat, scales up with spaCy, AI detection, T5, and embeddings
- **9 built-in personas** — slack-casual, pr-review, confluence-docs, jira-ticket, email-professional, blog-post, technical-docs, executive-summary, internal-references
- **Hot-reload** — persona files reload automatically on edit via watchfiles
- **Semantic persona search** — find personas by description using FastEmbed embeddings

## Quick Links

- [Installation](installation.md) — get phraseturner running in under a minute
- [Quickstart](quickstart.md) — analyse your first text with a persona
- [API Reference](api-reference.md) — full tool documentation
- [Persona Guide](persona-guide.md) — create and customise personas

## Requirements

- Python ≥ 3.12
- ~500MB memory (all models loaded)

## License

[MIT](https://github.com/geehexx/phraseturner/blob/main/LICENSE)
