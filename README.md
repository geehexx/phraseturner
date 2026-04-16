# phraseturner

[![CI](https://github.com/geehexx/phraseturner/actions/workflows/ci.yml/badge.svg)](https://github.com/geehexx/phraseturner/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-93%25-brightgreen)](https://github.com/geehexx/phraseturner)
[![PyPI](https://img.shields.io/pypi/v/phraseturner)](https://pypi.org/project/phraseturner/)
[![Python](https://img.shields.io/pypi/pyversions/phraseturner)](https://pypi.org/project/phraseturner/)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

📖 **[Documentation](https://geehexx.github.io/phraseturner)** | 🐛 **[Issues](https://github.com/geehexx/phraseturner/issues)**

Text analysis MCP server with configurable personas for readability, naturalness, tone, and AI detection.

phraseturner analyses text and returns structured feedback — readability scores, naturalness metrics, vocabulary analysis, tone assessment, AI detection signals, and per-sentence deep analysis via FLAN-T5. It **never rewrites text**; it provides feedback that a calling LLM uses to make its own rewriting decisions.

## Features

- **7 MCP tools** — `analyze`, `score`, `compare`, `list_personas`, `get_persona`, `create_persona`, `validate_persona`
- **Configurable personas** — Vale-compatible YAML rules extended with tone dimensions, brand voice, and LLM-evaluated rules
- **6-stage analysis pipeline** — classical NLP (spaCy, textstat, VADER), AI detection (is-it-slop), and FLAN-T5 deep analysis
- **Composite health score** — 0–100 score across 5 dimensions with letter grades (A–F)
- **Graceful degradation** — 5-tier operating model; works with just textstat, scales up with spaCy, AI detection, T5, and embeddings
- **9 built-in personas** — slack-casual, pr-review, confluence-docs, jira-ticket, email-professional, blog-post, technical-docs, executive-summary, internal-references
- **Hot-reload** — persona files reload automatically on edit via watchfiles
- **Semantic persona search** — find personas by description using FastEmbed embeddings

## Installation

Run directly without installing:

```bash
uvx phraseturner
```

Or install into a project:

```bash
uv pip install phraseturner
```

On first run, phraseturner downloads required models (spaCy `en_core_web_sm`, FLAN-T5 ONNX INT8) to `~/.cache/phraseturner/models/`.

## MCP Configuration

Add phraseturner to your MCP client's configuration:

```json
{
  "mcpServers": {
    "phraseturner": {
      "command": "uvx",
      "args": ["phraseturner"]
    }
  }
}
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PHRASETURNER_PERSONAS_DIR` | `~/.config/phraseturner/personas/` | Custom user persona directory |
| `PHRASETURNER_MODEL_DIR` | `~/.cache/phraseturner/models/` | Model download directory |
| `PHRASETURNER_DISABLE_T5` | `false` | Disable FLAN-T5 deep analysis |
| `PHRASETURNER_DISABLE_SLOP` | `false` | Disable AI detection |
| `PHRASETURNER_DISABLE_EMBED` | `false` | Disable FastEmbed semantic search |
| `PHRASETURNER_LOG_LEVEL` | `INFO` | Logging level |

## Quickstart

Once configured, ask your LLM to analyse text using the `analyze` tool:

```
Analyse this text with the slack-casual persona:

"Furthermore, it is imperative to note that the aforementioned factors
have been duly considered in the context of our ongoing deliberations."
```

phraseturner returns structured feedback:

```json
{
  "health_score": {
    "composite_score": 42.3,
    "letter_grade": "D",
    "dimensions": {
      "readability": { "score": 35.0, "status": "poor" },
      "naturalness": { "score": 28.0, "status": "poor" },
      "vocabulary": { "score": 55.0, "status": "warning" },
      "tone_compliance": { "score": 20.0, "status": "poor" }
    }
  },
  "sentences": [
    {
      "text": "Furthermore, it is imperative to note that...",
      "flags": [
        { "code": "PASSIVE_VOICE", "severity": "warning" },
        { "code": "FORMAL_IN_CASUAL", "severity": "error" }
      ]
    }
  ],
  "next_steps": [
    "Rewrite the flagged sentences, then call `score` to verify improvement",
    "Call `get_persona slack-casual` to review tone targets"
  ]
}
```

The calling LLM uses this feedback to rewrite the text itself — phraseturner only analyses, never rewrites.

## Tools

| Tool | Description | Latency |
|------|-------------|---------|
| `analyze` | Full text analysis with optional persona | ≤500ms |
| `score` | Quick health score (no T5 deep analysis) | ≤50ms |
| `compare` | Compare original vs rewritten text | ≤800ms |
| `list_personas` | List available personas with optional search | ≤50ms |
| `get_persona` | Get full persona definition | ≤50ms |
| `create_persona` | Create a new persona from YAML | ≤50ms |
| `validate_persona` | Validate persona YAML without saving | ≤50ms |

## Personas

Personas are YAML files that define tone dimensions, brand voice, vocabulary rules, and analysis rules. phraseturner resolves personas from 4 directory tiers:

1. **Project** — `.phraseturner/personas/` (relative to cwd)
2. **User** — `~/.config/phraseturner/personas/` (or `PHRASETURNER_PERSONAS_DIR`)
3. **Remote** — `~/.cache/phraseturner/remote/` (future)
4. **Built-in** — bundled with the package

Higher tiers take precedence on name collisions.

## Requirements

- Python ≥ 3.12
- ~500MB memory (all models loaded)

## License

[MIT](LICENSE)
