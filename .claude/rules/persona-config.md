---
description: "Phraseturner persona authoring + loading. Personas are YAML config in data/personas/*.yaml — never hardcoded. Always loaded."
alwaysApply: true
---

# Persona Configuration

Personas drive weighting + thresholds for the scoring pipeline. They are YAML files hot-reloaded at runtime via watchfiles.

## Persona YAML shape

```yaml
name: technical-writer
description: Balanced readability + precision, formal tone
weights:
  readability: 0.30
  naturalness: 0.25
  sentiment_neutrality: 0.15
  lexical_diversity: 0.15
  slop_aversion: 0.15
thresholds:
  flesch_min: 50
  grade_level_max: 14
  lexical_diversity_min: 0.5
  slop_probability_max: 0.3
style_hints:
  prefer_voice: active
  avoid_jargon: false
  target_audience: practitioners
```

## Rules

- `weights` MUST sum to 1.0 (±0.001 tolerance) — validation rejects otherwise
- `thresholds` are inclusive upper/lower bounds
- `style_hints` are free-form string metadata for LLM-optional rewrite helpers (not scoring path)
- Persona `name` MUST match the filename (`data/personas/technical-writer.yaml` → `name: technical-writer`)
- Changes trigger a reload via watchfiles within ~100 ms; `touch data/personas/` to force reload

## Where to put persona-specific logic

**In the persona YAML:** weights, thresholds, style hints
**In code:** generic scoring logic that READS persona config

If you find yourself writing `if persona.name == "X"`, that's a signal the config surface is too narrow — add a new field to the YAML schema instead.
