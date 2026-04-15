# Persona Authoring Guide

This guide covers everything you need to create custom personas for phraseturner — from schema basics to advanced rule types, tone calibration, and channel overrides.

## What is a Persona?

A persona is a YAML file that defines how phraseturner analyses text. It sets tone targets, vocabulary rules, brand voice identity, and analysis rules for a specific writing context (Slack messages, PR reviews, executive summaries, etc.).

When you pass a persona to the `analyze` or `score` tools, phraseturner evaluates your text against that persona's rules and tone dimensions, producing compliance scores and actionable flags.

## The 4-Tier Directory System

phraseturner resolves personas from four directory tiers. When the same persona name exists in multiple tiers, the highest-precedence tier wins.

| Tier | Priority | Location | Use Case |
|------|----------|----------|----------|
| **Project** | Highest | `.phraseturner/personas/` (relative to cwd) | Team-shared personas committed to a repo |
| **User** | High | `~/.config/phraseturner/personas/` | Personal personas across all projects |
| **Remote** | Medium | `~/.cache/phraseturner/remote/` | Community personas (future) |
| **Built-in** | Lowest | Bundled in the package | 9 default personas shipped with phraseturner |

Override the user-tier directory with the `PHRASETURNER_PERSONAS_DIR` environment variable. The directory is created automatically on first startup if it does not exist.

**Precedence example:** If both the built-in tier and your project tier contain `slack-casual.yaml`, the project version is used.

---

## Schema Reference

A persona YAML file has these top-level blocks:

```yaml
# Required
name: my-persona          # Unique identifier (string, required)
version: "1.0.0"          # Semantic version (required, must match X.Y.Z)

# Optional metadata
description: >-           # Human-readable description (used for semantic search)
  Short description of what this persona is for.
author: your-name         # Author name
locale: en-GB             # Locale code
channels:                 # Target channels (list of enum values)
  - slack
  - email
audience:                 # Target audience
  expertise_level: intermediate   # beginner, intermediate, expert
  domain: engineering             # Subject domain
tags:                     # Searchable tags for discovery
  - casual
  - messaging

# Tone dimensions
tone:
  formality: 0.5          # 0.0–1.0 (default: 0.5)
  confidence: 0.5
  warmth: 0.5
  directness: 0.5
  energy: 0.5
  verbosity: 0.5

# Brand voice (optional)
brand_voice:
  persona_card: "..."
  personality_traits: [...]
  catchphrases: [...]
  forbidden_phrases: [...]
  prompt_scaffold: "..."

# Vocabulary (optional)
vocabulary:
  approved: [...]
  prohibited: [...]

# Analysis rules
rules: [...]

# Per-channel overrides (optional)
channel_overrides: {}

# Custom health score weights (optional)
health_score_weights:
  readability: 0.25
  naturalness: 0.30
  vocabulary: 0.20
  semantic_preservation: 0.15
  tone_compliance: 0.10
```

### Field Reference

#### `persona` Fields (Top-Level)

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `name` | string | Yes | — | Unique persona identifier |
| `version` | string | Yes | Must match `X.Y.Z` (semver) | Persona version |
| `description` | string | No | — | Human-readable description (used for semantic search) |
| `author` | string | No | — | Author name |
| `locale` | string | No | — | Locale code (e.g. `en-GB`, `en-US`) |
| `channels` | list[Channel] | No | Valid values: `slack`, `email`, `confluence`, `jira`, `pr-review`, `blog`, `docs`, `executive` | Target communication channels |
| `audience` | object | No | — | Target audience (see below) |
| `tags` | list[string] | No | — | Searchable tags for persona discovery |

#### `audience` Fields

| Field | Type | Description |
|-------|------|-------------|
| `expertise_level` | string | `beginner`, `intermediate`, or `expert` |
| `domain` | string | Subject domain (e.g. `engineering`, `marketing`, `legal`) |

#### `tone` Fields

| Field | Type | Default | Range | Description |
|-------|------|---------|-------|-------------|
| `formality` | float | 0.5 | 0.0–1.0 | Formal (1.0) vs casual (0.0) register |
| `confidence` | float | 0.5 | 0.0–1.0 | Assertive (1.0) vs tentative (0.0) voice |
| `warmth` | float | 0.5 | 0.0–1.0 | Warm/friendly (1.0) vs neutral/distant (0.0) |
| `directness` | float | 0.5 | 0.0–1.0 | Direct (1.0) vs indirect (0.0) communication |
| `energy` | float | 0.5 | 0.0–1.0 | High-energy (1.0) vs calm (0.0) delivery |
| `verbosity` | float | 0.5 | 0.0–1.0 | Verbose (1.0) vs concise (0.0) expression |

#### `brand_voice` Fields

| Field | Type | Description |
|-------|------|-------------|
| `persona_card` | string | Free-text description of the persona's character and voice |
| `personality_traits` | list[string] | Personality trait keywords (e.g. `["friendly", "authoritative"]`) |
| `catchphrases` | list[string] | Signature phrases the persona uses |
| `forbidden_phrases` | list[string] | Phrases the persona must never use |
| `prompt_scaffold` | string | Template scaffold for LLM prompt construction |

#### `vocabulary` Fields

| Field | Type | Description |
|-------|------|-------------|
| `approved` | list[string] | Words and phrases that are encouraged |
| `prohibited` | list[string] | Words and phrases that should be flagged |

#### `rules` Array — Common Fields

Every rule requires these fields:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | string | Yes | — | Unique rule identifier within the persona |
| `type` | RuleType | Yes | — | One of the 13 supported rule types |
| `level` | RuleLevel | No | `warning` | `error`, `warning`, or `suggestion` |
| `message` | string | No | — | Human-readable message when the rule triggers |
| `scope` | string | No | `text` | `text`, `sentence`, `paragraph`, `heading`, or `raw` |
| `examples` | object | No | — | Test examples (see [Rule Examples](#rule-examples-field)) |
| `channel` | Channel | No | — | Restrict this rule to a specific channel |
| `action` | object | No | — | Auto-fix suggestion: `replace`, `edit`, `remove`, or `suggest` |

#### `channel_overrides` Fields

| Field | Type | Description |
|-------|------|-------------|
| `tone` | ToneConfig | Tone dimension overrides for this channel |
| `rule_severity` | dict[string, RuleLevel] | Map of rule ID → severity override |

#### `health_score_weights` Fields

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| `readability` | float | 0.0–1.0 | Weight for readability dimension |
| `naturalness` | float | 0.0–1.0 | Weight for naturalness dimension |
| `vocabulary` | float | 0.0–1.0 | Weight for vocabulary dimension |
| `semantic_preservation` | float | 0.0–1.0 | Weight for semantic preservation dimension |
| `tone_compliance` | float | 0.0–1.0 | Weight for tone compliance dimension |

All five weights **must sum to 1.0** (±0.001 tolerance). Validation fails otherwise.

---

## Rule Types

phraseturner supports 13 rule types: 10 Vale-compatible types and 3 phraseturner extensions.

### Vale-Compatible Rule Types

These follow the same semantics as [Vale v3.14.1](https://vale.sh/docs/topics/styles/).

#### 1. `existence` — Flag Matching Tokens or Patterns

Flags text that contains any of the specified tokens or regex patterns.

```yaml
- id: no-jargon
  type: existence
  level: warning
  message: "Jargon detected — consider simpler alternatives."
  tokens:
    - synergy
    - leverage
    - paradigm
```

With regex patterns using `raw`:

```yaml
- id: no-passive-voice
  type: existence
  level: suggestion
  message: "Passive voice detected."
  scope: raw
  raw:
    - "\\b(?:was|were|been|being) \\w+ed\\b"
```

**Fields:** `tokens` (list of literal strings) and/or `raw` (list of regex patterns).

#### 2. `substitution` — Suggest Replacements

Flags a word or phrase and suggests a specific replacement via a swap map.

```yaml
- id: use-contractions
  type: substitution
  level: suggestion
  message: "Use contractions for a casual tone."
  swap:
    "do not": "don't"
    "cannot": "can't"
    "will not": "won't"
    "it is": "it's"
```

**Fields:** `swap` (dict mapping pattern → replacement).

#### 3. `occurrence` — Limit Token Count

Flags text when a metric exceeds a maximum count within a scope.

```yaml
- id: short-sentences
  type: occurrence
  level: suggestion
  message: "Sentence exceeds 20 words — keep it short."
  scope: sentence
  max: 20
  metric: words
```

**Fields:** `max` (integer), `metric` (string, e.g. `words`), `scope` (typically `sentence` or `paragraph`).

#### 4. `repetition` — Detect Duplicates

Flags repeated words or phrases within a scope.

```yaml
- id: no-word-repetition
  type: repetition
  level: warning
  message: "Repeated word detected within paragraph."
  scope: paragraph
  tokens:
    - "\\b(\\w+)\\b.*\\b\\1\\b"
```

**Fields:** `tokens` (patterns to detect repetition).

#### 5. `consistency` — Enforce Either/Or Choices

Ensures consistent usage when two forms exist (e.g. "colour" vs "color").

```yaml
- id: spelling-consistency
  type: consistency
  level: error
  message: "Inconsistent spelling — pick one form and use it throughout."
  either:
    colour: color
    organisation: organization
    analyse: analyze
```

**Fields:** `either` (dict mapping one form to its alternative). The rule flags text that uses both forms.

#### 6. `conditional` — If A Then B

Flags text where condition A is met but condition B is not.

```yaml
- id: abbreviation-defined
  type: conditional
  level: warning
  message: "Abbreviation used without prior definition."
  match: "\\bAPI\\b"
  tokens:
    - "Application Programming Interface"
```

**Fields:** `match` (regex for condition A), `tokens` (required context B).

#### 7. `capitalization` — Enforce Case Patterns

Checks heading or text capitalization against a pattern.

```yaml
- id: heading-title-case
  type: capitalization
  level: warning
  message: "Headings should use title case."
  scope: heading
  match: "(?:[A-Z][a-z]+ )+"
```

**Fields:** `match` (regex pattern for expected capitalization), `scope` (typically `heading`).

#### 8. `metric` — Formula Evaluation

Evaluates a readability or complexity formula against a threshold.

```yaml
- id: reading-level
  type: metric
  level: warning
  message: "Reading level too high for target audience."
  metric: flesch_kincaid_grade
  max: 12
```

**Fields:** `metric` (formula identifier), `max` (threshold).

#### 9. `sequence` — POS Tag Sequences

Detects specific part-of-speech tag sequences in sentences.

```yaml
- id: no-noun-stacking
  type: sequence
  level: suggestion
  message: "Noun stacking detected — consider restructuring."
  scope: sentence
  tokens:
    - "NOUN NOUN NOUN"
```

**Fields:** `tokens` (POS tag sequence patterns).

#### 10. `script` — External Scripts (Excluded in v1.0)

The `script` rule type (Vale Tengo scripts) is **not supported in v1.0** for security reasons. It is reserved for a future version.

### phraseturner Extension Rule Types

These three rule types are unique to phraseturner and extend beyond Vale's capabilities.

#### 11. `llm_eval` — FLAN-T5 Evaluated Rules

Evaluates text using the FLAN-T5 model with a custom prompt. Requires Operating Tier ≥ 3 (T5 loaded). Skipped with status `skipped` when T5 is unavailable.

```yaml
- id: check-tone-formal
  type: llm_eval
  level: warning
  message: "Text does not match expected formal tone."
  scope: sentence
  prompt: "Classify the tone of this text as formal, informal, or neutral: {text}"
  target: "formal"
  tolerance: 0.65
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `prompt` | string | FLAN-T5 prompt template. Use `{text}` as placeholder for the input text. |
| `target` | string | Expected T5 output label. |
| `tolerance` | float | Minimum confidence threshold (0.0–1.0). Below this, the rule is not triggered. |

#### 12. `tone` — Tone Dimension Threshold

Evaluates whether a computed tone dimension score falls within an acceptable range.

```yaml
- id: formality-check
  type: tone
  level: warning
  message: "Formality is below the minimum threshold for this persona."
  dimension: formality
  min: 0.6
```

```yaml
- id: verbosity-cap
  type: tone
  level: suggestion
  message: "Text is more verbose than the persona target."
  dimension: verbosity
  max: 20
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `dimension` | string | One of: `formality`, `confidence`, `warmth`, `directness`, `energy`, `verbosity` |
| `min` | float | Minimum acceptable score for the dimension |
| `max` | int/float | Maximum acceptable score (optional) |

#### 13. `brand_voice` — Brand Voice Compliance

Checks text against the persona's brand voice configuration — personality traits, catchphrases, and forbidden phrases.

```yaml
- id: brand-compliance
  type: brand_voice
  level: warning
  message: "Text does not align with brand voice guidelines."
```

This rule type uses the persona's `brand_voice` block automatically. No additional fields are needed beyond the common rule fields (`id`, `type`, `level`, `message`).

---

## Tone Dimensions

The `tone` block defines six dimensions that phraseturner uses to evaluate text against your persona's voice. Each dimension is a float from 0.0 to 1.0, where 0.5 is neutral.

### Formality (0.0–1.0)

Measures the register of the text — from casual conversation to formal prose.

| Value | Style | Indicators |
|-------|-------|------------|
| 0.0–0.3 | Casual | Contractions, slang, short sentences, emoji-friendly |
| 0.4–0.6 | Neutral | Standard prose, balanced register |
| 0.7–1.0 | Formal | No contractions, Latin abbreviations, passive constructions, nominalizations |

**Example personas:** `slack-casual` uses 0.2 (casual), `email-professional` uses 0.7 (formal).

### Confidence (0.0–1.0)

Measures how assertive or tentative the voice is.

| Value | Style | Indicators |
|-------|-------|------------|
| 0.0–0.3 | Tentative | Hedging words ("perhaps", "might", "seems"), qualifiers |
| 0.4–0.6 | Balanced | Mix of assertion and qualification |
| 0.7–1.0 | Assertive | Direct claims, no hedging, imperative mood |

**Example personas:** `pr-review` uses 0.6 (moderately assertive), `executive-summary` uses 0.7 (assertive).

### Warmth (0.0–1.0)

Measures the emotional temperature — from distant and neutral to warm and friendly.

| Value | Style | Indicators |
|-------|-------|------------|
| 0.0–0.3 | Distant | Impersonal, third-person, no emotional language |
| 0.4–0.6 | Neutral | Professional but approachable |
| 0.7–1.0 | Warm | First-person, empathetic language, positive sentiment |

**Example personas:** `slack-casual` uses 0.8 (warm), `pr-review` uses 0.4 (slightly cool — constructive, not chummy).

### Directness (0.0–1.0)

Measures how directly the text communicates its point.

| Value | Style | Indicators |
|-------|-------|------------|
| 0.0–0.3 | Indirect | Circumlocution, passive voice, buried conclusions |
| 0.4–0.6 | Balanced | Clear but diplomatic |
| 0.7–1.0 | Direct | Lead with the point, active voice, imperative |

**Example personas:** `pr-review` uses 0.8 (very direct — "Change X to Y"), `email-professional` uses 0.5 (balanced).

### Energy (0.0–1.0)

Measures the energy level of the writing — from calm and measured to enthusiastic.

| Value | Style | Indicators |
|-------|-------|------------|
| 0.0–0.3 | Calm | Measured pace, understated, no exclamation |
| 0.4–0.6 | Moderate | Standard energy |
| 0.7–1.0 | High-energy | Enthusiastic, dynamic verbs, shorter punchy sentences |

**Example personas:** `slack-casual` uses 0.7 (energetic), `technical-docs` uses 0.3 (calm and measured).

### Verbosity (0.0–1.0)

Measures how concise or verbose the text is.

| Value | Style | Indicators |
|-------|-------|------------|
| 0.0–0.3 | Concise | Short sentences, minimal filler, telegraphic |
| 0.4–0.6 | Moderate | Standard length |
| 0.7–1.0 | Verbose | Detailed explanations, longer sentences, thorough |

**Example personas:** `slack-casual` uses 0.3 (concise — Slack messages should be short), `confluence-docs` uses 0.6 (moderately detailed).

### Calibration Tips

1. **Start with a built-in persona** that is closest to your target voice, then adjust dimensions.
2. **Change one dimension at a time** and use the `score` tool to see the effect.
3. **Use the `analyze` tool** with `include_suggestions=true` to see which dimensions are causing flags.
4. **Extreme values** (0.0 or 1.0) are rarely appropriate — most real writing falls in the 0.2–0.8 range.
5. **Test with real text samples** from your target context, not synthetic examples.

---

## Brand Voice Configuration

The `brand_voice` block gives your persona a distinct identity beyond tone dimensions. It is used by `brand_voice` rules and provides context for LLM-evaluated analysis.

### Walkthrough: Creating a Brand Voice

Here is a step-by-step example for a developer advocacy persona:

```yaml
brand_voice:
  persona_card: >-
    DevRel Dana is a senior developer advocate who explains complex
    technical concepts with clarity and enthusiasm. She uses analogies,
    avoids jargon without explanation, and always includes actionable
    next steps.

  personality_traits:
    - enthusiastic
    - clear
    - empathetic
    - technically accurate
    - action-oriented

  catchphrases:
    - "Let's break this down"
    - "Here's the key insight"
    - "Try this in your terminal"

  forbidden_phrases:
    - "It's simple"
    - "Just do X"
    - "Obviously"
    - "As everyone knows"

  prompt_scaffold: >-
    You are DevRel Dana, a developer advocate writing for intermediate
    developers. Be enthusiastic but precise. Always explain why, not
    just how. End with a concrete next step.
```

**How each field is used:**

- `persona_card` — Provides a character description for brand voice compliance checks.
- `personality_traits` — Keywords checked against the text's detected style and tone.
- `catchphrases` — Signature phrases that are encouraged (not required).
- `forbidden_phrases` — Phrases that trigger flags when detected in text.
- `prompt_scaffold` — A template that can be used by calling LLMs to adopt this persona's voice.

### Adding a Brand Voice Rule

Once you have a `brand_voice` block, add a rule to enforce it:

```yaml
rules:
  - id: brand-voice-check
    type: brand_voice
    level: warning
    message: "Text does not align with the brand voice guidelines."
```

The `brand_voice` rule type automatically uses the persona's `brand_voice` block — no additional configuration needed.

---

## Rule Examples Field

Every rule can include an `examples` field with `valid` and `invalid` test cases. phraseturner validates these during persona validation (`validate_persona` tool):

- `valid` examples must **not** trigger the rule
- `invalid` examples **must** trigger the rule

If any example behaves unexpectedly, validation returns an `EXAMPLE_MISMATCH` error.

### Adding Examples to a Rule

```yaml
rules:
  - id: no-jargon
    type: existence
    level: warning
    message: "Jargon detected — consider simpler alternatives."
    tokens:
      - synergy
      - leverage
      - paradigm
    examples:
      valid:
        - "The teams worked together on the project."
        - "We used the framework to build the feature."
      invalid:
        - "We need to leverage our synergies."
        - "This represents a paradigm shift."
```

### Why Use Examples?

1. **Self-documenting** — Examples show exactly what the rule catches and what it allows.
2. **Regression testing** — When you modify a rule's patterns, examples catch unintended changes.
3. **Validation** — The `validate_persona` tool runs examples automatically and reports mismatches.

### Tips

- Include at least 2 valid and 2 invalid examples per rule.
- For regex-based rules (`raw` field), test edge cases in your examples.
- For `substitution` rules, include examples with and without the swap targets.

---

## Channel Overrides

Channel overrides let you customise tone dimensions and rule severity for specific communication channels. This is useful when a single persona needs slight adjustments per channel.

### Syntax

```yaml
channel_overrides:
  slack:
    tone:
      formality: 0.2
      energy: 0.8
    rule_severity:
      email-sentence-length: suggestion   # Downgrade from warning to suggestion on Slack
  email:
    tone:
      formality: 0.7
      warmth: 0.5
    rule_severity:
      slack-no-formal-language: suggestion  # Formal language is fine in email
```

### How Overrides Work

- `tone` — Replaces the persona's base tone dimensions for that channel. Only the dimensions you specify are overridden; others keep their base values.
- `rule_severity` — Maps rule IDs to new severity levels for that channel. The rule still runs, but its severity changes.

### When to Use Channel Overrides

Use channel overrides when you have a persona that works across multiple channels but needs minor adjustments:

- A "team communication" persona that is casual on Slack but slightly more formal in email
- A "documentation" persona that is strict on Confluence but relaxed in JIRA comments
- A "review" persona that treats sentence length as an error in PRs but a suggestion in Slack

If the differences between channels are large, consider creating separate personas instead.

---

## Complete Example

Here is a full persona YAML file with annotations:

```yaml
# --- Required metadata ---
name: devrel-blog
version: "1.0.0"
description: >-
  Developer advocacy blog posts — enthusiastic, clear, and technically
  accurate. Targets intermediate developers. Favours active voice,
  concrete examples, and actionable conclusions.
author: phraseturner
locale: en-US

# --- Discovery ---
channels:
  - blog
  - docs
audience:
  expertise_level: intermediate
  domain: engineering
tags:
  - developer-advocacy
  - blog
  - technical-writing

# --- Tone targets ---
tone:
  formality: 0.4      # Conversational but not slangy
  confidence: 0.7      # Assertive — "do this" not "you might consider"
  warmth: 0.7          # Friendly and approachable
  directness: 0.7      # Lead with the point
  energy: 0.6          # Enthusiastic but not breathless
  verbosity: 0.5       # Balanced — explain enough but don't ramble

# --- Brand voice ---
brand_voice:
  persona_card: >-
    A senior developer advocate who makes complex topics accessible.
    Uses analogies, code examples, and always ends with next steps.
  personality_traits:
    - enthusiastic
    - clear
    - empathetic
    - technically precise
  catchphrases:
    - "Let's break this down"
    - "Here's what's happening under the hood"
  forbidden_phrases:
    - "It's simple"
    - "Just do X"
    - "Obviously"
    - "Trivially"

# --- Vocabulary ---
vocabulary:
  approved:
    - straightforward
    - practical
    - hands-on
    - step-by-step
  prohibited:
    - synergy
    - leverage
    - paradigm shift
    - best-in-class

# --- Rules ---
rules:
  # Vale-compatible: flag jargon
  - id: no-jargon
    type: existence
    level: warning
    message: "Corporate jargon detected — use plain language."
    tokens:
      - synergy
      - leverage
      - paradigm shift
      - best-in-class
      - move the needle
    examples:
      valid:
        - "This approach improves performance by 30%."
      invalid:
        - "We need to leverage our core competencies."

  # Vale-compatible: suggest contractions
  - id: use-contractions
    type: substitution
    level: suggestion
    message: "Use contractions for a conversational tone."
    swap:
      "do not": "don't"
      "cannot": "can't"
      "will not": "won't"
      "it is": "it's"
      "we are": "we're"

  # Vale-compatible: sentence length
  - id: sentence-length
    type: occurrence
    level: warning
    message: "Sentence exceeds 25 words — consider splitting."
    scope: sentence
    max: 25
    metric: words

  # Vale-compatible: consistent spelling
  - id: spelling-consistency
    type: consistency
    level: error
    message: "Inconsistent spelling — pick one form."
    either:
      colour: color
      organisation: organization

  # phraseturner extension: tone check
  - id: formality-floor
    type: tone
    level: warning
    message: "Text is too formal for a blog post."
    dimension: formality
    min: 0.0
    max: 0.6

  # phraseturner extension: brand voice
  - id: brand-voice-check
    type: brand_voice
    level: warning
    message: "Text does not match the DevRel brand voice."

# --- Channel overrides ---
channel_overrides:
  docs:
    tone:
      formality: 0.5    # Slightly more formal for docs
      energy: 0.4        # Calmer for reference docs
    rule_severity:
      use-contractions: suggestion  # Contractions optional in docs

# --- Custom health score weights ---
health_score_weights:
  readability: 0.25
  naturalness: 0.25
  vocabulary: 0.20
  semantic_preservation: 0.15
  tone_compliance: 0.15
```

### Validating Your Persona

Before saving, validate your persona YAML:

```
# Via the validate_persona MCP tool
validate_persona(yaml_content="<your YAML here>")

# Or create it directly (validates automatically)
create_persona(yaml_content="<your YAML here>")
```

The validator checks:

- Required fields (`name`, `version`)
- Semver format for `version`
- Tone dimensions in 0.0–1.0 range
- Valid rule types and levels
- No duplicate rule IDs
- Health score weights sum to 1.0
- Rule examples pass/fail correctly
- No secrets detected in the YAML content

### Error Codes

| Code | Meaning |
|------|---------|
| `MISSING_REQUIRED_FIELD` | A required field is missing |
| `INVALID_FIELD_TYPE` | A field has the wrong type |
| `INVALID_ENUM_VALUE` | A field value is not in the allowed set |
| `INVALID_RANGE` | A numeric field is outside 0.0–1.0 |
| `INVALID_SEMVER` | Version string does not match X.Y.Z |
| `INVALID_REGEX` | A regex pattern in a rule is invalid |
| `DUPLICATE_RULE_ID` | Two rules share the same ID |
| `INVALID_RULE_TYPE` | Rule type is not one of the 13 supported types |
| `EXAMPLE_MISMATCH` | A rule example did not behave as expected |
| `INVALID_WEIGHTS_SUM` | Health score weights do not sum to 1.0 |
| `SECRET_DETECTED` | Possible API key or token found in the YAML |
