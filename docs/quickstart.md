# Quickstart

This guide walks you through your first text analysis with phraseturner.

## Basic Analysis

Ask your LLM to analyse text using the `analyze` tool:

```
Analyse this text: "The quick brown fox jumps over the lazy dog."
```

phraseturner returns a structured response with a health score, per-sentence flags, and next steps:

```json
{
  "health_score": {
    "composite_score": 75.0,
    "letter_grade": "B",
    "dimensions": {
      "readability": {"score": 85.0, "status": "good"},
      "naturalness": {"score": 70.0, "status": "good"},
      "vocabulary": {"score": 65.0, "status": "warning"}
    }
  },
  "next_steps": [
    "Call `analyze` with `include_suggestions=true` for improvement hints"
  ]
}
```

## Using Personas

Personas define tone, vocabulary, and style rules for specific writing contexts. Analyse text against a persona:

```
Analyse this text with the slack-casual persona:

"Furthermore, it is imperative to note that the aforementioned factors
have been duly considered in the context of our ongoing deliberations."
```

The response includes persona alignment scores and tone deltas showing where the text diverges from the persona's targets.

### List Available Personas

```
List all available personas
```

phraseturner ships with 9 built-in personas: `slack-casual`, `pr-review`, `confluence-docs`, `jira-ticket`, `email-professional`, `blog-post`, `technical-docs`, `executive-summary`, and `internal-references`.

### Find a Persona by Description

```
Find a persona for writing casual team messages
```

Semantic search matches your description against persona definitions using FastEmbed embeddings.

## Quick Score vs Full Analysis

For a fast quality check without per-sentence deep analysis, use the `score` tool:

```
Score this text: "We should probably maybe consider looking into this issue soon."
```

The `score` tool skips FLAN-T5 deep analysis and returns results in ≤50ms — useful for rapid iteration loops where the calling LLM rewrites and re-checks repeatedly.

## Comparing Versions

After rewriting text, use the `compare` tool to measure improvement:

```
Compare the original and rewritten versions:

Original: "It is imperative to note that the system has been updated."
Rewritten: "The system is updated."
```

The response includes semantic similarity, per-dimension deltas, and an overall improvement score.

## Next Steps

- [API Reference](api-reference.md) — full documentation for all 7 tools
- [Persona Guide](persona-guide.md) — create custom personas with tone dimensions and rules
- [Installation](installation.md) — environment variables and model configuration
