# API Reference

Complete reference documentation for all 7 phraseturner MCP tools. Each tool is registered via FastMCP 3.0+ with structured annotations, input/output schemas, and contextual `next_steps` guidance.

All tools follow the **6-component description framework** (purpose, constraints, side effects, usage guidance, follow-up steps, error handling) to enable effective LLM-driven tool discovery.

---

## Common Concepts

### Error Response Schema

All tools return structured errors using the `ToolError` schema:

```json
{
  "code": "ERROR_CODE",
  "message": "Human-readable error description.",
  "details": { }
}
```

### Error Catalog

| Code | Category | Trigger |
|------|----------|---------|
| `TEXT_TOO_LONG` | Input | Text exceeds 8 000 tokens |
| `TEXT_TOO_SHORT` | Input | Empty or whitespace-only text |
| `PERSONA_NOT_FOUND` | Persona | No persona matches the name or query |
| `PERSONA_EXISTS` | Persona | A persona with the same name already exists in the user directory |
| `PERSONA_VALIDATION_FAILED` | Persona | YAML content fails schema validation |
| `INVALID_FOCUS_MODE` | Input | Unknown focus mode value |
| `INVALID_YAML` | Persona | YAML parse error |
| `MODEL_LOAD_FAILED` | System | A required model failed to load |
| `SPACY_UNAVAILABLE` | System | spaCy model is not installed |
| `T5_TIMEOUT` | System | FLAN-T5 inference exceeded 200 ms per sentence |
| `STAGE_FAILED` | Pipeline | An analysis stage threw an exception |
| `INTERNAL_ERROR` | System | Unexpected server error |

### Health Score Grades

| Grade | Composite Score Range |
|-------|-----------------------|
| A | ≥ 85 |
| B | 70 – 84 |
| C | 55 – 69 |
| D | 40 – 54 |
| F | < 40 |

### Dimension Status

| Status | Score Range |
|--------|------------|
| good | > 70 |
| warning | 40 – 70 |
| poor | < 40 |

### Operating Tiers

| Tier | Models Loaded | Capabilities |
|------|---------------|-------------|
| 0 | textstat only | Readability scores only |
| 1 | + spaCy | + vocabulary, tone, sentence analysis |
| 2 | + is-it-slop | + AI detection, naturalness scoring |
| 3 | + FLAN-T5 ONNX | + per-sentence deep analysis |
| 4 | + FastEmbed | + semantic search, persona alignment, semantic preservation |

---

## `analyze` — Full Pipeline Analysis

Comprehensive text quality analysis against an optional persona. Runs the full 6-stage pipeline (input validation → classical NLP → AI detection → FLAN-T5 → score aggregation → output formatting).

### Annotations

| Annotation | Value |
|------------|-------|
| `title` | Analyse Text |
| `readOnlyHint` | `true` |
| `destructiveHint` | `false` |
| `idempotentHint` | `true` |
| `openWorldHint` | `false` |

### Latency Target

≤ 500 ms for texts of ≤ 5 sentences (at Tier 3+).

### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `text` | `string` | Yes | — | Text to analyse (1–8 000 tokens). |
| `persona` | `string \| null` | No | `null` | Persona name or semantic query for persona resolution. |
| `focus` | `string` | No | `"full"` | Restrict analysis to a dimension: `full`, `readability`, `naturalness`, `persona_compliance`. |
| `include_suggestions` | `boolean` | No | `false` | Include up to 5 actionable analysis hints. |
| `original_text` | `string \| null` | No | `null` | Original text for semantic preservation scoring. |
| `response_format` | `string` | No | `"detailed"` | Response verbosity: `concise` or `detailed`. |

### Output Schema

**Detailed mode** returns `AnalysisResult`:

| Field | Type | Description |
|-------|------|-------------|
| `health_score` | `HealthScore` | Composite score (0–100), letter grade, per-dimension breakdown. |
| `sentences` | `list[SentenceAnalysis]` | Per-sentence flags, T5 analysis, readability grade, word count, and metrics. |
| `persona_alignment` | `PersonaAlignment \| null` | Overall compliance, tone deltas, rule violations/passes. Present when a persona is provided. |
| `suggestions` | `list[Suggestion] \| null` | Up to 5 hints ranked by impact. Present when `include_suggestions=true`. |
| `next_steps` | `list[string]` | 1–3 contextual follow-up suggestions. |
| `metadata` | `AnalysisMetadata` | Model versions, latency, token count, operating tier, degradation status. |

**Concise mode** returns `ConciseAnalysisResult`:

| Field | Type | Description |
|-------|------|-------------|
| `health_score` | `HealthScore` | Same as detailed. |
| `flags_summary` | `FlagsSummary` | Counts per severity (`error_count`, `warning_count`, `suggestion_count`) and up to 5 `top_flags`. |
| `next_steps` | `list[string]` | 1–3 contextual follow-up suggestions. |
| `metadata` | `AnalysisMetadata` | Same as detailed. |

### Error Codes

| Code | When |
|------|------|
| `TEXT_TOO_LONG` | Input exceeds 8 000 tokens. |
| `TEXT_TOO_SHORT` | Input is empty or whitespace. |
| `PERSONA_NOT_FOUND` | Specified persona does not exist. |
| `INVALID_FOCUS_MODE` | Unknown focus mode value. |
| `STAGE_FAILED` | A pipeline stage failed — partial results returned with `degraded: true`. |

### JSON Example

**Request:**

```json
{
  "text": "Furthermore, it is imperative to note that the aforementioned factors have been duly considered.",
  "persona": "slack-casual",
  "include_suggestions": true
}
```

**Response (detailed):**

```json
{
  "health_score": {
    "composite_score": 42.3,
    "letter_grade": "D",
    "dimensions": {
      "readability": { "score": 35.0, "status": "poor", "weight": 0.25 },
      "naturalness": { "score": 28.0, "status": "poor", "weight": 0.30 },
      "vocabulary": { "score": 55.0, "status": "warning", "weight": 0.20 },
      "semantic_preservation": null,
      "tone_compliance": { "score": 20.0, "status": "poor", "weight": 0.10 }
    }
  },
  "sentences": [
    {
      "index": 0,
      "text": "Furthermore, it is imperative to note that...",
      "flags": [
        { "code": "PASSIVE_VOICE", "severity": "warning", "message": "Passive construction: 'have been considered'" },
        { "code": "FORMAL_IN_CASUAL", "severity": "error", "message": "Formal markers in casual persona" }
      ],
      "t5_analysis": {
        "style_class": "formal",
        "style_confidence": 0.94,
        "ai_pattern": "formulaic-transition",
        "ai_pattern_confidence": 0.78,
        "sentence_function": "claim",
        "sentence_function_confidence": 0.72,
        "tone": { "formality": "high", "confidence": "high", "directness": "low" },
        "persona_compliance": "major-violation",
        "persona_issue": "formal register in casual persona",
        "core_meaning": "factors were considered",
        "paraphrase_hint": null
      }
    }
  ],
  "persona_alignment": {
    "overall_compliance": 0.20,
    "tone_deltas": {
      "formality": { "target": 0.2, "actual": 0.9, "delta": -0.7 },
      "warmth": { "target": 0.8, "actual": 0.2, "delta": -0.6 }
    },
    "rule_violations": 3,
    "rule_passes": 0
  },
  "suggestions": [
    {
      "sentence_index": 0,
      "flag_code": "FORMAL_IN_CASUAL",
      "hint": "Replace formal transition 'Furthermore' with casual alternative",
      "impact": 0.85
    }
  ],
  "next_steps": [
    "Rewrite the flagged sentence using casual language, then call `score` to verify improvement",
    "Call `get_persona slack-casual` to review the full tone targets for this persona",
    "Consider splitting the long sentence into two shorter ones for better readability"
  ],
  "metadata": {
    "model_versions": { "spacy": "3.8.4", "t5": "flan-t5-base-int8", "fastembed": "bge-small-en-v1.5" },
    "latency_ms": 312.5,
    "token_count": 15,
    "operating_tier": 4,
    "t5_available": true
  }
}
```

---

## `score` — Quick Health Score

Returns a health score without FLAN-T5 deep analysis. Runs the quick path: Stage 0 → Stage 1 ∥ Stage 2 → Stage 4 → Stage 5 (skips Stage 3).

### Annotations

| Annotation | Value |
|------------|-------|
| `title` | Quick Health Score |
| `readOnlyHint` | `true` |
| `destructiveHint` | `false` |
| `idempotentHint` | `true` |

### Latency Target

≤ 50 ms for texts of ≤ 5 sentences.

### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `text` | `string` | Yes | — | Text to score (1–8 000 tokens). |
| `persona` | `string \| null` | No | `null` | Persona name or semantic query. Applies persona-specific weights if provided. |

### Output Schema

| Field | Type | Description |
|-------|------|-------------|
| `composite_score` | `float` | Overall score 0–100. |
| `letter_grade` | `string` | A / B / C / D / F. |
| `dimensions` | `dict[string, DimensionScore \| null]` | Per-dimension scores with status and weight. |
| `metadata` | `object` | Latency, token count, operating tier. `t5_available` is always `false` for this tool. |
| `next_steps` | `list[string]` | 1–3 contextual follow-up suggestions. |

### Error Codes

| Code | When |
|------|------|
| `TEXT_TOO_LONG` | Input exceeds 8 000 tokens. |
| `TEXT_TOO_SHORT` | Input is empty or whitespace. |
| `PERSONA_NOT_FOUND` | Specified persona does not exist. |

### JSON Example

**Request:**

```json
{
  "text": "The quick brown fox jumps over the lazy dog. It was a bright cold day in April, and the clocks were striking thirteen."
}
```

**Response:**

```json
{
  "composite_score": 72.5,
  "letter_grade": "B",
  "dimensions": {
    "readability": { "score": 80.0, "status": "good", "weight": 0.25 },
    "naturalness": { "score": 65.0, "status": "warning", "weight": 0.30 },
    "vocabulary": { "score": 75.0, "status": "good", "weight": 0.20 },
    "semantic_preservation": null,
    "tone_compliance": { "score": 60.0, "status": "warning", "weight": 0.10 }
  },
  "metadata": {
    "latency_ms": 12.3,
    "token_count": 42,
    "operating_tier": 4,
    "t5_available": false
  },
  "next_steps": [
    "Score is B — call `analyze` with `include_suggestions=true` to identify specific improvement areas",
    "Naturalness is in warning range — consider varying sentence length and structure"
  ]
}
```

---

## `compare` — Original vs Rewrite Comparison

Analyses both original and rewritten text, computes per-dimension deltas, semantic similarity (cosine via `bge-small-en-v1.5`), sentence alignment, and an overall improvement score.

### Annotations

| Annotation | Value |
|------------|-------|
| `title` | Compare Original vs Rewrite |
| `readOnlyHint` | `true` |
| `destructiveHint` | `false` |
| `idempotentHint` | `true` |

### Latency Target

≤ 800 ms.

### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `original` | `string` | Yes | — | Original text (1–8 000 tokens). |
| `rewritten` | `string` | Yes | — | Rewritten text (1–8 000 tokens). |
| `persona` | `string \| null` | No | `null` | Persona name or semantic query. Includes persona compliance deltas when provided. |
| `response_format` | `string` | No | `"detailed"` | Response verbosity: `concise` or `detailed`. |

### Output Schema

**Detailed mode** returns `ComparisonResult`:

| Field | Type | Description |
|-------|------|-------------|
| `semantic_similarity` | `float` | Cosine similarity (0.0–1.0) between original and rewritten embeddings. |
| `health_score_delta` | `dict[string, DimensionDelta]` | Per-dimension original score, rewritten score, and delta. |
| `overall_improvement` | `float` | Aggregate improvement across all dimensions. |
| `sentence_alignment` | `list[SentenceAlignment]` | Maps original sentence indices to rewritten sentence indices with similarity. |
| `persona_compliance_delta` | `DimensionDelta \| null` | Persona compliance change. Present when a persona is provided. |
| `next_steps` | `list[string]` | 1–3 contextual follow-up suggestions. |
| `metadata` | `object` | Latency, operating tier. |

**Concise mode** returns `ConciseComparisonResult`:

| Field | Type | Description |
|-------|------|-------------|
| `semantic_similarity` | `float` | Same as detailed. |
| `overall_improvement` | `float` | Same as detailed. |
| `next_steps` | `list[string]` | 1–3 contextual follow-up suggestions. |
| `metadata` | `object` | Same as detailed. |

### Error Codes

| Code | When |
|------|------|
| `TEXT_TOO_LONG` | Either input exceeds 8 000 tokens. |
| `TEXT_TOO_SHORT` | Either input is empty or whitespace. |
| `PERSONA_NOT_FOUND` | Specified persona does not exist. |

### JSON Example

**Request:**

```json
{
  "original": "Furthermore, it is imperative to note that the aforementioned factors have been duly considered.",
  "rewritten": "We looked at all the key factors.",
  "persona": "slack-casual"
}
```

**Response (detailed):**

```json
{
  "semantic_similarity": 0.87,
  "health_score_delta": {
    "readability": { "original": 45.0, "rewritten": 78.0, "delta": 33.0 },
    "naturalness": { "original": 30.0, "rewritten": 72.0, "delta": 42.0 },
    "vocabulary": { "original": 60.0, "rewritten": 70.0, "delta": 10.0 },
    "tone_compliance": { "original": 25.0, "rewritten": 80.0, "delta": 55.0 }
  },
  "overall_improvement": 35.0,
  "sentence_alignment": [
    { "original_index": 0, "rewritten_indices": [0, 1], "similarity": 0.82 }
  ],
  "persona_compliance_delta": { "original": 0.20, "rewritten": 0.85, "delta": 0.65 },
  "next_steps": [
    "Rewrite improved all dimensions — consider running `score` on the final version to confirm",
    "Semantic similarity is 0.87 — meaning is well preserved"
  ],
  "metadata": {
    "latency_ms": 645.2,
    "operating_tier": 4
  }
}
```

---

## `list_personas` — List Available Personas

Returns summaries of all personas across the 4-tier directory hierarchy, with optional semantic search and tag filtering.

### Annotations

| Annotation | Value |
|------------|-------|
| `title` | List Personas |
| `readOnlyHint` | `true` |
| `idempotentHint` | `true` |

### Latency Target

≤ 50 ms.

### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | `string \| null` | No | `null` | Semantic search query. When provided, results are ranked by cosine similarity via FastEmbed. Falls back to substring matching at Tier < 4. |
| `tags` | `list[string] \| null` | No | `null` | Filter to personas matching all specified tags. |

### Output Schema

Returns `list[PersonaSummary]`:

| Field | Type | Description |
|-------|------|-------------|
| `name` | `string` | Persona name. |
| `description` | `string \| null` | Short description. |
| `tags` | `list[string]` | Associated tags. |
| `channels` | `list[string]` | Supported channels (e.g. `slack`, `email`, `docs`). |
| `tier` | `string` | Source tier: `built-in`, `remote`, `user`, or `project`. |
| `version` | `string` | SemVer version string. |

### Error Codes

This tool does not produce tool-specific errors. An empty list is returned when no personas match.

### JSON Example

**Request:**

```json
{
  "query": "casual messaging"
}
```

**Response:**

```json
[
  {
    "name": "slack-casual",
    "description": "Casual tone for Slack messages and team chat",
    "tags": ["casual", "messaging", "team"],
    "channels": ["slack"],
    "tier": "built-in",
    "version": "1.0.0"
  },
  {
    "name": "email-professional",
    "description": "Professional tone for business email",
    "tags": ["professional", "email", "business"],
    "channels": ["email"],
    "tier": "built-in",
    "version": "1.0.0"
  }
]
```

---

## `get_persona` — Get Full Persona Detail

Returns the complete definition of a persona by exact name or semantic query. When the name does not match exactly, falls back to semantic search and returns the closest match.

### Annotations

| Annotation | Value |
|------------|-------|
| `title` | Get Persona Detail |
| `readOnlyHint` | `true` |
| `idempotentHint` | `true` |

### Latency Target

≤ 50 ms.

### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `name_or_query` | `string` | Yes | — | Exact persona name or a semantic query string. |

### Output Schema

Returns `PersonaDetail`:

| Field | Type | Description |
|-------|------|-------------|
| `name` | `string` | Persona name. |
| `version` | `string` | SemVer version. |
| `description` | `string \| null` | Description. |
| `tone` | `ToneConfig` | 6 tone dimensions (formality, confidence, warmth, directness, energy, verbosity), each 0.0–1.0. |
| `brand_voice` | `BrandVoiceConfig \| null` | Persona card, personality traits, catchphrases, forbidden phrases, prompt scaffold. |
| `vocabulary` | `VocabularyConfig` | Approved and prohibited word lists. |
| `rules` | `list[RuleConfig]` | All rules with id, type, level, and type-specific fields. |
| `channel_overrides` | `dict[string, ChannelOverride]` | Per-channel tone and rule severity overrides. |
| `health_score_weights` | `HealthScoreWeights \| null` | Custom dimension weights (must sum to 1.0). |
| `tier` | `string` | Source tier. |

### Error Codes

| Code | When |
|------|------|
| `PERSONA_NOT_FOUND` | No persona matches the name or query. |

### JSON Example

**Request:**

```json
{
  "name_or_query": "slack-casual"
}
```

**Response:**

```json
{
  "name": "slack-casual",
  "version": "1.0.0",
  "description": "Casual tone for Slack messages and team chat",
  "tone": {
    "formality": 0.2,
    "confidence": 0.6,
    "warmth": 0.8,
    "directness": 0.7,
    "energy": 0.7,
    "verbosity": 0.3
  },
  "brand_voice": null,
  "vocabulary": {
    "approved": [],
    "prohibited": ["aforementioned", "hereby", "pursuant"]
  },
  "rules": [
    {
      "id": "no-formal-transitions",
      "type": "existence",
      "level": "error",
      "message": "Avoid formal transitions in casual Slack messages: '%s'",
      "tokens": ["Furthermore", "Moreover", "In addition", "Consequently"]
    }
  ],
  "channel_overrides": {},
  "health_score_weights": null,
  "tier": "built-in"
}
```

---

## `create_persona` — Create New Persona

Validates YAML content against the persona schema and writes a new persona file to the user persona directory (`~/.config/phraseturner/personas/` or `PHRASETURNER_PERSONAS_DIR`).

### Annotations

| Annotation | Value |
|------------|-------|
| `title` | Create Persona |
| `readOnlyHint` | `false` |
| `destructiveHint` | `false` |

### Latency Target

≤ 50 ms.

### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `yaml_content` | `string` | Yes | — | Complete persona definition in YAML format. |

### Output Schema

Returns `PersonaCreateResult`:

| Field | Type | Description |
|-------|------|-------------|
| `name` | `string` | Name of the created persona. |
| `file_path` | `string` | Absolute path to the written YAML file. |
| `validation` | `ValidationResult` | Validation outcome with `valid`, `errors`, and `warnings` lists. |

### Error Codes

| Code | When |
|------|------|
| `PERSONA_VALIDATION_FAILED` | YAML content fails schema validation. The `details` field contains a list of structured validation errors. |
| `PERSONA_EXISTS` | A persona with the same name already exists in the user directory. |
| `INVALID_YAML` | YAML content cannot be parsed. |

### Side Effects

Writes a `.yaml` file to the user persona directory. The hot-reload watcher picks up the new file automatically.

### JSON Example

**Request:**

```json
{
  "yaml_content": "persona:\n  name: my-custom\n  version: \"1.0.0\"\n  description: Custom persona for internal docs\ntone:\n  formality: 0.7\n  confidence: 0.6\n  warmth: 0.5\n  directness: 0.6\n  energy: 0.4\n  verbosity: 0.5\nrules:\n  - id: no-jargon\n    type: existence\n    level: warning\n    message: \"Avoid jargon: '%s'\"\n    tokens:\n      - synergy\n      - leverage\n      - paradigm"
}
```

**Response:**

```json
{
  "name": "my-custom",
  "file_path": "/home/user/.config/phraseturner/personas/my-custom.yaml",
  "validation": {
    "valid": true,
    "errors": [],
    "warnings": []
  }
}
```

---

## `validate_persona` — Validate Persona YAML

Validates persona YAML content against the schema without writing any file. Use this to check for errors before calling `create_persona`.

### Annotations

| Annotation | Value |
|------------|-------|
| `title` | Validate Persona |
| `readOnlyHint` | `true` |
| `idempotentHint` | `true` |

### Latency Target

≤ 50 ms.

### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `yaml_content` | `string` | Yes | — | Persona YAML content to validate. |

### Output Schema

Returns `ValidationResult`:

| Field | Type | Description |
|-------|------|-------------|
| `valid` | `boolean` | `true` if the YAML passes all validation checks. |
| `errors` | `list[ValidationError]` | Structural and schema errors. Each entry has `path` (JSON path), `code`, and `message`. |
| `warnings` | `list[ValidationError]` | Non-blocking warnings (e.g. `SECRET_DETECTED`). Same structure as errors. |

**Validation error codes:**

| Code | Description |
|------|-------------|
| `MISSING_REQUIRED_FIELD` | A required field is absent. |
| `INVALID_FIELD_TYPE` | A field has the wrong type. |
| `INVALID_ENUM_VALUE` | A field value is not in the allowed set. |
| `INVALID_RANGE` | A numeric field is outside 0.0–1.0. |
| `INVALID_SEMVER` | The version string is not valid SemVer. |
| `INVALID_REGEX` | A rule pattern is not valid regex. |
| `DUPLICATE_RULE_ID` | Two rules share the same `id`. |
| `INVALID_RULE_TYPE` | A rule `type` is not one of the 13 supported types. |
| `EXAMPLE_MISMATCH` | A rule's `examples.valid` triggered the rule, or `examples.invalid` did not. |
| `INVALID_WEIGHTS_SUM` | Custom `health_score_weights` do not sum to 1.0. |
| `SECRET_DETECTED` | The YAML appears to contain an API key, token, or password. |

### Error Codes

| Code | When |
|------|------|
| `INVALID_YAML` | YAML content cannot be parsed. |

### JSON Example

**Request:**

```json
{
  "yaml_content": "persona:\n  name: bad-persona\ntone:\n  formality: 1.5"
}
```

**Response:**

```json
{
  "valid": false,
  "errors": [
    {
      "path": "persona.version",
      "code": "MISSING_REQUIRED_FIELD",
      "message": "Field 'version' is required in the persona block."
    },
    {
      "path": "tone.formality",
      "code": "INVALID_RANGE",
      "message": "Tone dimension 'formality' must be between 0.0 and 1.0, got 1.5."
    }
  ],
  "warnings": []
}
```

---

## Tool Summary

| Tool | Read-Only | Idempotent | Latency Target | Side Effects |
|------|-----------|------------|----------------|-------------|
| `analyze` | Yes | Yes | ≤ 500 ms | None |
| `score` | Yes | Yes | ≤ 50 ms | None |
| `compare` | Yes | Yes | ≤ 800 ms | None |
| `list_personas` | Yes | Yes | ≤ 50 ms | None |
| `get_persona` | Yes | Yes | ≤ 50 ms | None |
| `create_persona` | No | No | ≤ 50 ms | Writes YAML file to user persona directory |
| `validate_persona` | Yes | Yes | ≤ 50 ms | None |
