# phraseturner Usage Patterns

Guidance for using phraseturner tools effectively. Load this when working with text analysis, quality scoring, or persona-based writing feedback.

## Tool Selection

### When to use `analyze`

Use `analyze` for comprehensive feedback when you need to understand *why* text scores poorly. It runs the full 6-stage pipeline including FLAN-T5 deep analysis, returning per-sentence flags, tone assessment, AI pattern detection, and actionable suggestions.

Best for:
- First pass on a new piece of text
- Understanding specific issues (passive voice, formality mismatch, AI patterns)
- Getting suggestions before rewriting
- Persona compliance assessment

Use `response_format: "concise"` when you only need the health score and flags summary without per-sentence breakdowns.

### When to use `score`

Use `score` for fast quality checks during iterative rewriting. It skips FLAN-T5 deep analysis and returns only the composite score, letter grade, and per-dimension breakdown.

Best for:
- Quick pass/fail checks after a rewrite
- Monitoring quality during multi-round editing
- Batch scoring multiple text variants
- When latency matters (≤50ms vs ≤500ms for `analyze`)

### When to use `compare`

Use `compare` after rewriting to measure improvement and verify meaning preservation. It runs both texts through the pipeline and computes deltas.

Best for:
- Verifying a rewrite improved quality
- Checking semantic similarity (meaning preservation)
- Measuring per-dimension improvement
- Deciding whether to keep a rewrite or try again

## Common Workflows

### Analyse → Rewrite → Compare → Score

The standard iterative improvement workflow:

1. `analyze` with persona and `include_suggestions=true` — get detailed feedback
2. Rewrite the text using the flags and suggestions as guidance
3. `compare` original vs rewritten — verify improvement and meaning preservation
4. `score` the final version — confirm it meets the quality bar

### Quick Quality Gate

For fast pass/fail checks (e.g., before posting a message):

1. `score` with persona — get composite score and grade
2. If grade is A or B, proceed
3. If grade is C or below, call `analyze` for detailed feedback

### Persona Discovery

When you don't know which persona to use:

1. `list_personas` with a semantic query describing the context (e.g., "casual team chat")
2. `get_persona` on the best match to review its tone targets and rules
3. Use that persona name in subsequent `analyze` or `score` calls

### Content Hygiene Check

To detect internal tooling references that shouldn't appear in user-facing documents:

1. `analyze` with persona `internal-references`
2. Review flags for memory URIs, agent paths, and internal tool names
3. Remove or replace flagged content

## Persona Selection Guide

### By Communication Channel

| Channel | Persona | Notes |
|---------|---------|-------|
| Slack / Teams | `slack-casual` | Low formality, contractions encouraged |
| Email | `email-professional` | Moderate formality, warm but professional |
| PR reviews | `pr-review` | Direct, technical, constructive feedback |
| JIRA tickets | `jira-ticket` | Concise, actionable, specific |
| Confluence / wiki | `confluence-docs` | Clear structure, moderate formality |
| Blog posts | `blog-post` | Engaging, accessible, varied sentence structure |
| Technical docs | `technical-docs` | Precise, formal, comprehensive |
| Executive comms | `executive-summary` | High-level, confident, concise |

### By Writing Goal

| Goal | Persona | Why |
|------|---------|-----|
| Sound more human | `slack-casual` or `blog-post` | High naturalness targets, varied structure |
| Be more professional | `email-professional` | Balanced formality and warmth |
| Write clearly | `technical-docs` | Readability and precision focus |
| Be concise | `jira-ticket` or `executive-summary` | Low verbosity targets |
| Detect AI patterns | (any persona) | All personas flag AI-typical patterns |
| Catch internal leaks | `internal-references` | Flags memory URIs, agent paths, tool names |

## response_format Recommendations

| Situation | Format | Reason |
|-----------|--------|--------|
| First analysis of new text | `detailed` | Need per-sentence breakdown to guide rewriting |
| Quick check after rewrite | `concise` | Only need score and top-level flags |
| Comparing versions | `detailed` | Want sentence alignment and per-dimension deltas |
| Batch processing | `concise` | Minimise response size for throughput |
| Debugging persona rules | `detailed` | Need to see which rules triggered on which sentences |

## Interpreting next_steps

Every tool response includes a `next_steps` field with 1–3 contextual suggestions. These are generated based on the analysis results and guide you toward the most impactful next action.

Common patterns:
- "Call `analyze` with `include_suggestions=true`" — score is low, need detailed feedback
- "Call `score` to verify improvement" — after a rewrite, confirm the quality improved
- "Call `get_persona <name>` to review tone targets" — persona compliance is low
- "Vary sentence length and structure" — naturalness score is poor
- "Text quality is good — no immediate action needed" — score is A, nothing to fix

Follow the `next_steps` suggestions to maintain an efficient analysis-rewrite loop.

## Environment Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PHRASETURNER_PERSONAS_DIR` | `~/.config/phraseturner/personas/` | Custom user persona directory |
| `PHRASETURNER_DISABLE_T5` | `false` | Disable FLAN-T5 (reduces to Tier 2) |
| `PHRASETURNER_DISABLE_SLOP` | `false` | Disable AI detection model |
| `PHRASETURNER_DISABLE_EMBED` | `false` | Disable FastEmbed (no semantic search) |
| `PHRASETURNER_MODEL_DIR` | `~/.cache/phraseturner/models/` | Model download directory |
| `PHRASETURNER_LOG_LEVEL` | `INFO` | Logging verbosity |

Set `PHRASETURNER_DISABLE_T5=true` for faster startup if you only need quick scoring.
