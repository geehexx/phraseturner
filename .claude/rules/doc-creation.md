---
description: "When to create new markdown files vs edit existing ones vs write a memory. Always loaded. Prevents doc proliferation and unapproved ADRs."
alwaysApply: true
---

# Document Creation Discipline

New markdown files have high long-term cost — they fragment the knowledge surface, drift out of sync, and are hard to find. Most "documents" the agent wants to create are actually memories, rule updates, or amendments to existing docs. Default to NOT creating new files.

## Decision tree before creating any new .md file

Ask in order; first YES wins:

1. **Could this be a lessons-inbox entry?** Session observations, near-misses, "worth improving" notes → append to `.claude/lessons-inbox/YYYY-MM.md`. No approval needed; these are ephemeral until `/meta-review` consolidates.

2. **Could this be a memory?** Cross-session facts, research findings, architectural decisions the agent re-derives → `basic-memory` / auto-loaded MEMORY.md. Persistent, searchable, zero markdown proliferation.

3. **Could this amend an existing rule or skill?** Expansion of a concept already covered by `.claude/rules/*.md` or a skill body → Edit the existing file. Don't fork.

4. **Could this extend an agent body?** Agent-specific protocol or red-flag list → Edit `.claude/agents/{name}.md`. Don't create a sibling file.

5. **Is this a genuinely new rule/skill/agent for a recurring workflow?** → Create, but ONLY after explicit user approval of the file path + description + scope.

## Categories that REQUIRE user approval before creation

- **ADRs** (`docs/adrs/`) — architecture decisions are commitments; they need deliberation, not drive-by authoring.
- **New `.claude/rules/*.md`** — always-loaded rules cost context on every turn.
- **New `.claude/agents/*.md`** — agents are dispatchable and visible in routing.
- **New `.claude/skills/*/SKILL.md`** — skills compete for activation budget.
- **New `.claude/commands/*.md`** — slash commands are user-facing surface.
- **Top-level `docs/*.md`** in any product repo — product documentation is public.
- **New `README.md`** anywhere — duplicates project-level README.

## Categories that do NOT require approval

- Appending to `lessons-inbox/YYYY-MM.md` (append-only, consolidated later).
- Writing to `basic-memory` (searchable memory surfaces, TTL-managed).
- Appending to `auto-loaded memory/MEMORY.md` (personal, not git-tracked).
- Editing an existing rule/skill/agent/doc with a surgical change.
- Temporary working files under `.claude/state/`, `/tmp/`, or scratch directories.
- Commit messages, PR descriptions, Linear ticket bodies.
- **Co-located README.md next to code it documents** (e.g. `tests/X/README.md`, `scripts/X/README.md`, `infra/stacks/X/README.md`). Structural, not proliferation — one README per self-contained code directory is Python/Node convention.

## When presenting a new-file proposal

Use this shape so the user can approve concisely:

```
Proposing new file:
- Path: [repo-relative path]
- Type: rule | skill | agent | command | doc | adr
- Why existing file won't do: [specific reason]
- Size target: [line count]
- Outline: [3-5 bullet content summary]

Approve? [Yes / No / Amend]
```

## Plans directory — frontmatter expected

`plans/*.md` files (this repo) SHOULD carry YAML frontmatter matching one of three entity types: `session_handoff`, `workstream_plan`, `bot_review_triage`. Schema definitions can be added to `data/basic-memory/schemas/` if structural enforcement is wanted — not required today. Templated skeleton for session handoffs: `.claude/templates/session-handoff.md.tmpl`.

Enforcement is WARN-ONLY via the `check-plan-frontmatter` lefthook pre-commit step. The hook prints warnings for missing frontmatter but never blocks a commit — deliberate, because mid-crash-recovery plans should never be blocked by schema ceremony. Set `PLAN_FRONTMATTER_STRICT=1` to make the hook exit non-zero (CI experiments only).

The minimum for each type:
- `session_handoff` → `session_date: YYYY-MM-DD` and `one_sentence_pickup: <string>`
- `workstream_plan` → `summary: <string>`
- `bot_review_triage` → `pr_url: <full https URL>`

File-name hints that drive automatic type inference when `entity:` is missing:
- `*handoff*.md` → session_handoff
- `*bot-review*.md` → bot_review_triage
- everything else → workstream_plan

## Anti-patterns to reject

- "I'll write a design doc for this" without asking — use an inbox entry or memory note instead.
- Creating an ADR because a decision feels important — the user decides what's ADR-worthy.
- Creating a new rule for a one-off workflow — amend an existing rule or add a memory.
- Creating a per-session scratchpad doc — use `.claude/state/` or `/tmp/`.
- Duplicating content into a new file because it's tangential — reference the canonical location instead.

## Enforcement

The orchestrator Phase 1 (CLARIFY) must call this rule out loud for any task whose output might be a new markdown file. If the answer is "new rule / skill / agent / ADR", stop and present the approval prompt before any Write tool call.

Sub-agents inherit this discipline. A sub-agent proposing a new file returns `ESCALATE: clarify` per `delegation-contract.md` §4 rather than creating it.

## Meta

This rule was itself created after a 2026-05-10 session where the agent created ~15 markdown files across repos without discussing them first. Treat that as the pattern to prevent.
