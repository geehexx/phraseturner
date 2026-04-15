# Installation

## Recommended: uvx (no install needed)

Run phraseturner directly without installing:

```bash
uvx phraseturner
```

This downloads and runs phraseturner in an isolated temporary environment. Models are downloaded on first run to `~/.cache/phraseturner/models/`.

## Install with uv

```bash
uv pip install phraseturner
```

Then run:

```bash
phraseturner
```

## Install with pip

```bash
pip install phraseturner
```

## MCP Client Configuration

Add phraseturner to your MCP client's `mcp.json`:

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

For Kiro IDE, add this to your workspace or global MCP settings.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PHRASETURNER_PERSONAS_DIR` | `~/.config/phraseturner/personas/` | Custom user persona directory |
| `PHRASETURNER_MODEL_DIR` | `~/.cache/phraseturner/models/` | Model download directory |
| `PHRASETURNER_DISABLE_T5` | `false` | Disable FLAN-T5 deep analysis |
| `PHRASETURNER_DISABLE_SLOP` | `false` | Disable AI detection |
| `PHRASETURNER_DISABLE_EMBED` | `false` | Disable FastEmbed semantic search |
| `PHRASETURNER_LOG_LEVEL` | `INFO` | Logging level |
| `PHRASETURNER_WATCH_ENABLED` | `true` | Enable persona hot-reload |
| `PHRASETURNER_MAX_TOKENS` | `8000` | Maximum input token limit |

## Model Downloads

On first run, phraseturner downloads:

- **spaCy `en_core_web_sm`** (~14MB) — sentence splitting, POS tagging, dependency parsing
- **FLAN-T5 ONNX INT8** (~220MB) — per-sentence deep analysis
- **FastEmbed `bge-small-en-v1.5`** (~33MB) — semantic persona search and text similarity

Models are cached in `PHRASETURNER_MODEL_DIR` and reused on subsequent runs. Disable individual models with the `PHRASETURNER_DISABLE_*` environment variables to reduce memory usage and download time.

## Operating Tiers

phraseturner degrades gracefully based on available models:

| Tier | Models | Capabilities |
|------|--------|-------------|
| 0 | textstat only | Readability scores only |
| 1 | + spaCy | + vocabulary, tone, sentence analysis |
| 2 | + is-it-slop | + AI detection |
| 3 | + FLAN-T5 | + per-sentence deep analysis |
| 4 | + FastEmbed | + semantic search, persona alignment |
