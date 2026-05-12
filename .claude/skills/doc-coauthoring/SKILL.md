---
name: doc-coauthoring
description: "Improves documentation quality using the reader-testing pattern: a fresh perspective reads docs as a new user would, identifying gaps, ambiguities, and missing context that the author is too close to see. Use when writing or reviewing specs, READMEs, ADRs, or any technical documentation. Especially valuable for cv-builder specs written by the same people who implement them — author assumptions are invisible to the author. Covers undefined terms, missing why explanations, broken cross-references, outdated tool names, and EARS pattern compliance. Produces a structured improvement report with specific rewrites. Activates on: review docs, test documentation, doc quality, reader test, improve documentation, documentation review, spec review, README review, ADR review, is this clear, would a new developer understand this."
metadata:
  category: quality
  complexity: 2
  activation_examples:
    - "review this spec as if you've never seen the codebase"
    - "test the documentation for the search pipeline"
    - "would a new developer understand this ADR?"
    - "doc quality check on the requirements.md"
    - "improve the README for the vendor enrichment pipeline"
  related_steering:
    - spec-creation-guide
    - review-protocol
---

# Doc Co-Authoring Skill

Improves documentation quality using the reader-testing pattern. Adapted from Anthropic skills (Apache 2.0). A fresh perspective reads the document as a new user would, identifying gaps, ambiguities, and missing context that the author is too close to see.

Use this skill whenever you write or review specs, READMEs, ADRs, or any technical documentation. The reader-testing pattern is especially valuable for cv-builder specs because they are written by the same people who implement them — the author's assumptions are invisible to them.

## When to Activate

- Before marking a spec phase complete — does the requirements.md actually communicate the intent?
- When writing a new ADR — would a future developer understand the decision and its context?
- When a README hasn't been updated after a major refactor
- When onboarding a new team member and they ask "where do I start?"
- When a stakeholder says "I don't understand what this does"
- After any significant architecture change that affects multiple documents

## Step 1: Define the Reader Persona

Before reading the document, define who the reader is. The persona determines what prior knowledge to assume and what gaps to flag.

**Common personas for cv-builder documentation**:

| Persona | Prior knowledge | What they need |
|---------|----------------|----------------|
| New developer | Python + async, but not cv-builder | Architecture overview, setup steps, where to start |
| Procurement team | Business context, not technical | What the system does, how to use it, what it costs |
| External auditor | Compliance frameworks, not the codebase | Evidence of controls, decision rationale, audit trail |
| Future maintainer | General software engineering | Why decisions were made, what to avoid, how to extend |

For cv-builder specs, the default persona is **new developer joining the team** — they know Python and async/await but have never seen the codebase, the ATS scoring rubric, or the Nova Act scraper architecture.

State the persona explicitly before reading:

```
Persona: New developer joining the cv-builder team.
Prior knowledge: Python 3.12, async/await, pytest, Pydantic.
No knowledge of: cv-builder architecture, the scoring rubric, the Nova Act scraper stack, LanceDB.
```

## Step 2: First-Pass Read

Read the document as the persona, noting issues as you go. Do NOT fix anything yet — just annotate.

Use `Read` to read the document:

```python
Read(path=".claude/specs/{spec-name}/requirements.md")
```

While reading, flag these categories of issues:

### Terms used without definition

Any term that the persona would not know. Examples in cv-builder docs:
- "RRF" — Reciprocal Rank Fusion, not obvious to a new developer
- "RenderCV YAML shape" — a specific rendercv convention, not standard
- "LanceDB" — newer vector store, not universally known
- "EARS pattern" — a requirements notation, not universally known

Flag: `[UNDEFINED TERM: "RRF" — define or link to ADR-0037]`

### Steps that assume prior knowledge

Instructions that skip a prerequisite step. Examples:
- "Run the enrichment pipeline" — but how? What command? What environment?
- "Update the taxonomy" — but where is it? What format?
- "Deploy to staging" — but what are the prerequisites?

Flag: `[ASSUMED KNOWLEDGE: how to run the enrichment pipeline — add command or link]`

### Missing "why" explanations

Documents that explain *what* and *how* but not *why*. The "why" is what makes decisions defensible and maintainable.

Examples of missing "why":
- "Always use `asyncio.gather` for parallel Bedrock calls" — why? (Because Semaphore(5) caps rate; gather with the semaphore keeps burst spend predictable)
- "Use `BaseSettings` not `BaseModel`" — why? (Because `BaseModel` silently ignores env vars)
- "Use `.distinct()` on M2M queries" — why? (Because M2M joins produce duplicates)

Flag: `[MISSING WHY: explain why sync_to_async is required here]`

### Broken cross-references

Links or references that don't resolve:
- `See ADR-0042` — but ADR-0042 doesn't exist
- `See the search pipeline docs` — but there's no link
- `As described in requirements.md` — but which section?

```python
# Check if referenced ADRs exist
Bash (ls)(path="docs/adrs")
Bash (grep/rg)(
    pattern="ADR-\\d+",
    path="{document-path}"
)
```

Flag: `[BROKEN REFERENCE: ADR-0042 does not exist — did you mean ADR-0040?]`

### Outdated information

Content that was accurate when written but is now stale:
- References to OpenTofu (replaced by CDK — ADR-0040)
- References to `executePwsh` (replaced by `Bash`)
- References to `readFile` (replaced by `Read`)
- References to `pip` (replaced by `uv`)

```python
Bash (grep/rg)(
    pattern="executePwsh|readFile|grepSearch|strReplace|pip install|terraform|tofu",
    path="{document-path}"
)
```

Flag: `[OUTDATED: executePwsh replaced by Bash]`

## Step 3: Comprehension Test

After the first-pass read, close the document and answer these questions from memory. Do NOT look back.

1. **What is this document about?** (1 sentence)
2. **What should I do after reading this?** (next action)
3. **What are the 3 most important things to know?**
4. **What questions do I still have?**

Write down the answers before looking back. Then compare:

- If you can't answer question 1 → the document lacks a clear purpose statement
- If you can't answer question 2 → the document lacks a clear call to action
- If your "3 most important things" don't match the author's intent → the document buries the lede
- If you have many questions → the document has significant gaps

This test is most useful for READMEs and ADRs, where the reader needs to quickly understand the purpose and take action.

## Step 4: Gap Analysis

Compare what the reader understood (Step 3) vs what the author intended. Identify the gaps.

**Gap categories**:

| Gap type | Example | Fix |
|----------|---------|-----|
| Missing prerequisite | "Run the tests" without explaining how to set up the environment | Add setup section |
| Implicit assumption | "The vendor is active" without defining what "active" means | Add definition |
| Missing example | "Use EARS patterns" without showing one | Add example |
| Missing error case | "Call the API" without explaining what to do if it fails | Add error handling section |
| Missing context | "This replaces the old approach" without explaining what the old approach was | Add context |

For cv-builder specs specifically, check:

```python
# Does the requirements.md use EARS patterns?
Bash (grep/rg)(
    pattern="The system shall|When .* the system shall|While .* the system shall",
    path="{requirements-path}"
)

# Does the ADR follow MADR format?
Bash (grep/rg)(
    pattern="## Status|## Context|## Decision|## Consequences",
    path="{adr-path}"
)

# Does the README have a quickstart section?
Bash (grep/rg)(
    pattern="## Quick[Ss]tart|## Getting [Ss]tarted|## Setup",
    path="README.md"
)
```

## Step 5: Improvement Report

Produce a structured improvement report with specific, actionable fixes. Do NOT just list problems — provide the fix for each one.

```markdown
## Documentation Review: {document-name}

**Persona**: {persona used}
**Date**: {date}
**Overall assessment**: CLEAR / NEEDS MINOR WORK / NEEDS SIGNIFICANT WORK

### Comprehension Test Results
- What is this about? "{answer}" — {MATCHES INTENT / MISSES INTENT}
- Next action? "{answer}" — {CLEAR / UNCLEAR}
- 3 most important things: {list} — {MATCHES / DIVERGES from author intent}
- Remaining questions: {list}

### Issues Found

#### Undefined Terms (N found)
1. **"{term}"** (line N) — Add definition: "{suggested definition}"
2. **"{term}"** (line N) — Link to: {ADR or doc}

#### Missing "Why" Explanations (N found)
1. **"{what}"** (line N) — Add: "{suggested why explanation}"

#### Broken References (N found)
1. **"{reference}"** (line N) — Fix: {correct reference}

#### Outdated Content (N found)
1. **"{outdated text}"** (line N) — Replace with: "{current text}"

#### Missing Sections
1. **{section name}** — Add: {what it should contain}

### Suggested Rewrites

For each significant issue, provide the rewritten text:

**Before**:
> {original text}

**After**:
> {improved text}

### ADR Compliance (for specs)
- EARS patterns used: {YES / NO — N requirements need rewriting}
- British English for taxonomy content: {YES / NO}
- Decision-makers are human only: {YES / NO}
- No internal tooling references: {YES / NO}
```

## cv-builder-Specific Patterns

### EARS Patterns for Requirements

cv-builder requirements use EARS (Easy Approach to Requirements Syntax) notation. When reviewing requirements.md, check that each requirement follows one of these patterns:

```
Ubiquitous:    The system shall {action}.
Event-driven:  When {trigger}, the system shall {action}.
State-driven:  While {state}, the system shall {action}.
Optional:      Where {feature}, the system shall {action}.
Unwanted:      If {condition}, then the system shall {action}.
```

Flag any requirement that uses vague language:
- "The system should..." → "should" is not a requirement; use "shall"
- "The system might..." → not a requirement
- "The system will..." → ambiguous; use "shall" for requirements

### ADR Format for Decisions

cv-builder ADRs use MADR format. Every ADR must have:

```markdown
# ADR-NNNN: {Title}

## Status
{Proposed | Accepted | Deprecated | Superseded by ADR-XXXX}

## Context
{Why this decision was needed}

## Decision
{What was decided}

## Consequences
{What changes as a result — positive and negative}
```

Flag ADRs missing any of these sections.

### British English for Taxonomy Content

All LLM-generated taxonomy content uses British English. When reviewing taxonomy-related documentation, check for American spellings:

```python
Bash (grep/rg)(
    pattern="\\b(color|organization|analyze|recognize|behavior|center|fiber)\\b",
    path="{document-path}"
)
# Flag any matches — should be colour, organisation, analyse, recognise, behaviour, centre, fibre
```

### No Internal Tooling References

User-facing documents (ADRs, READMEs, docs/) must not reference internal tooling:

```python
Bash (grep/rg)(
    pattern="memory://|\\.claude/|basic-memory|Task tool|steering file|kiro-meta",
    path="docs/"
)
# Any match is a violation — replace with plain language
```
