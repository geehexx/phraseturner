---
name: feature-planning
description: "Structured feature planning with premise challenge and failure mode analysis. Use when starting a new feature spec, evaluating a user request, or planning a complex implementation. Challenges the premise of the request, identifies scope modes (minimal/standard/full), maps failure modes, and produces a structured implementation plan. Ideal before invoking the spec-writer agent — this skill produces the input for that workflow. Covers ADR compliance checks, blast radius analysis, and cross-domain dependency mapping. Activates on: plan feature, spec for, how should we implement, what's the best approach, design this feature, challenge this idea, is this the right approach, feature planning, premise check, scope analysis, failure mode mapping, implementation planning, architecture review, blast radius, scope modes."
metadata:
  category: planning
  complexity: 3
  activation_examples:
    - "plan the feature for vendor comparison export"
    - "how should we implement the saved search feature?"
    - "challenge this idea: add real-time notifications"
    - "what's the best approach for the taxonomy enrichment pipeline?"
    - "spec for the vendor onboarding flow"
  related_steering:
    - spec-creation-guide
    - orchestration
---

# Feature Planning Skill

A structured workflow for challenging premises, scoping work, and producing implementation plans before writing a single line of code. Adapted from garrytan/gstack office-hours methodology (MIT).

**Plan mode vs this skill — not the same.** Plan Mode is a Claude Code permission posture (`EnterPlanMode` / `ExitPlanMode` tools, read-only during planning). This skill runs regardless of permission mode and supplies forcing questions plan mode does not: premise challenge, scope modes, failure-mode map, ADR compliance check. Use together for PR-level work. See `rules/plan-mode.md` for when to enter plan mode.

## When to Activate

- Starting a new feature spec or requirements document
- Evaluating a user request before committing to implementation
- Planning a complex multi-file change (Level 3+)
- When a task feels underspecified or the scope is unclear
- Before invoking the `spec-writer` agent — this skill produces the input for that agent

## Step 1: Premise Challenge

Before planning anything, challenge the premise of the request with these six forcing questions. Answer each one honestly — the answers shape everything that follows.

**1. What problem does this actually solve?**
Not the stated problem — the real one. "Add export to CSV" might actually be solving "procurement team can't share results with stakeholders." The real problem might have a better solution.

**2. Who specifically benefits, and how do we know they want this?**
Name the user role (procurement team, buyer admin, vendor). What evidence exists that this is a pain point? Is this in a JIRA ticket with user feedback, or is it an assumption?

**3. What's the simplest version that delivers 80% of the value?**
Strip away everything that isn't core. If the feature is "vendor comparison with export, filtering, and sharing," the 80% version might just be "side-by-side vendor comparison." Build that first.

**4. What breaks if we build this wrong?**
Think about data integrity, security, performance, and user trust. For cv-builder: does this touch auth/RBAC? Does it expose cross-tenant data? Does it affect search quality scores?

**5. What are we NOT building, and why?**
Explicit scope exclusions prevent scope creep. Write them down. "We are not building real-time collaboration in this iteration because it requires WebSocket infrastructure (ADR not yet written)."

**6. What would make us abandon this in 3 months?**
If the feature requires a technology we don't control, depends on a third-party API with no SLA, or requires ongoing manual curation — name that risk now.

## Step 2: Scope Modes

After the premise challenge, choose a scope mode. Present all three to the user and get explicit sign-off before proceeding.

### Minimal
Core functionality only. No edge cases. Fastest path to value.
- Single happy path
- No error recovery beyond basic validation
- No tests beyond the critical path
- No documentation beyond inline comments
- Estimated effort: 1–2 days

### Standard (default)
Core + common edge cases + tests + docs.
- Happy path + 2–3 error paths
- Unit tests for business logic, integration test for the API endpoint
- Docstrings on public functions
- ADR if a new architectural pattern is introduced
- Estimated effort: 3–5 days

### Full
Complete implementation with all edge cases, monitoring, and rollback plan.
- All error paths handled
- Property-based tests (Hypothesis) for invariants
- Performance benchmarks
- Monitoring/alerting hooks
- Rollback plan documented
- Estimated effort: 1–2 weeks

## Step 3: Architecture Review (Level 3+ tasks)

For any task touching more than 3 files or introducing a new pattern:

1. **Check existing ADRs** — `Bash (grep/rg)(pattern="keyword", path="docs/adrs")`. Key constraints: ADR-0006 (async-native), ADR-0013 (JWT httpOnly cookies), ADR-0023 (real PostgreSQL for tests), ADR-0025 (camelCase schemas), ADR-0032 (EmbeddingService singleton).

2. **Identify affected files** — use `Bash` (grep for symbol) and `Bash` (grep for callers) to map the blast radius before touching anything.

3. **Check basic-memory for prior decisions** — `mcp_basic_memory_search_notes(query="feature domain keywords")`. Prior research may already answer the key questions.

4. **Identify the layered architecture touch points**:
   - Entry layer: `src/cv_builder/cli/` — click/typer commands
   - Service layer: `{app}/services.py` — business logic
   - Model layer: `{app}/models.py` — ORM + QuerySets
   - Schema layer: `{app}/schemas.py` — Pydantic v2 with camelCase

5. **Check for cross-domain dependencies** — does this touch both backend and frontend? Both search and selection? If yes, plan the interface contract first (OpenAPI schema) before implementing either side.

## Step 4: Failure Mode Mapping

For each viable approach, map the failure modes before committing to one.

| Failure Mode | Likelihood | Impact | Mitigation |
|---|---|---|---|
| N+1 ORM queries | Medium | High (latency) | `select_related` / `prefetch_related` in `sync_to_async` block |
| Cross-tenant data leak | Low | Critical | Always filter by `request.auth.organization` |
| Async boundary violation | Medium | High (500 errors) | Fetch + serialise inside single `sync_to_async` call |
| Missing `.distinct()` on M2M | High | Medium (duplicates) | Always add `.distinct()` to M2M filter queries |
| Rate limit bypass | Low | Medium | Apply `check_rate_limit` to all auth endpoints |

Add feature-specific failure modes to this table. For each: what breaks, rollback plan, monitoring needed.

**Rollback plan**: For any database migration, document the reverse migration. For any API contract change, document the deprecation path. For any search pipeline change, document how to revert the weights.

## Step 5: Implementation Plan

Produce a structured output with these fields. This becomes the input for the `spec-writer` agent.

```
## Implementation Plan

**Feature**: [name]
**Chosen scope**: [Minimal / Standard / Full]
**Rationale**: [why this scope]

**Key decisions**:
- [decision 1 — e.g., "Use existing CamelSchema base class, not a new schema pattern"]
- [decision 2 — e.g., "Add to vendors/routers.py, not a new router file"]
- [decision 3 — e.g., "No new ADR needed — follows ADR-0006 async pattern"]

**Files to create/modify**:
- `backend/src/cv_builder/{app}/routers.py` — add endpoint
- `backend/src/cv_builder/{app}/services.py` — add service method
- `backend/src/cv_builder/{app}/schemas.py` — add response schema
- `backend/tests/unit/{app}/test_{feature}.py` — unit tests
- `frontend/components/{Feature}Component.vue` — UI component (if applicable)

**Estimated complexity**: Level [1-5]
**Estimated effort**: [X days]
**Blocked by**: [any dependencies or prerequisites]
**Not in scope**: [explicit exclusions]
```

## cv-builder-Specific Patterns

- **EARS patterns for acceptance criteria**: When writing acceptance criteria, use EARS format: "WHEN [trigger] THE SYSTEM SHALL [response]." See `spec-creation-guide.md` for full EARS syntax.
- **Async safety**: Bedrock/Nova Act calls are async. Never mix sync boto3 into the event loop. Use `asyncio.Semaphore` to cap concurrent API calls — Nova Act throttles hard.
- **ADR-0023 test requirements**: All tests use real PostgreSQL via testcontainers. Never SQLite. Use `@pytest.mark.django_db` for database tests.
- **ADR-0025 camelCase**: All Pydantic response schemas inherit from `CamelSchema` with `alias_generator=to_camel`. Python uses snake_case; JSON uses camelCase.
- **Three-Tier Isolation**: If this feature touches `.claude/` configuration, it must never leak into `pyproject.toml`, `backend/tests/`, or `.pre-commit-config.yaml`.
