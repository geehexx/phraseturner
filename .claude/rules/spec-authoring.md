---
description: "EARS acceptance criteria + traceability IDs for specs"
globs: ["specs/**", "docs/**/*.md"]
alwaysApply: false
---

# Spec Authoring — EARS and Acceptance Criteria

Reference: `docs/specs/` for phraseturner specs.

## EARS — the 5 patterns

Every acceptance criterion uses ONE of these keyword shapes. Mix them freely within a requirement; each criterion must use a single shape.

| Pattern | Form | Example |
|---|---|---|
| **Ubiquitous** | `THE <system> SHALL <response>` | THE search API SHALL return results in <500ms P95. |
| **Event-driven** | `WHEN <trigger>, THE <system> SHALL <response>` | WHEN a user submits a query, THE backend SHALL log request_id, user_id, and latency. |
| **State-driven** | `WHILE <state>, THE <system> SHALL <response>` | WHILE the user is unauthenticated, THE UI SHALL hide admin routes. |
| **Unwanted** | `IF <trigger>, THEN THE <system> SHALL <response>` | IF authentication fails, THEN THE API SHALL return 401 without leaking user existence. |
| **Optional** | `WHERE <feature active>, THE <system> SHALL <response>` | WHERE rate limiting is enabled, THE API SHALL reject requests exceeding 30/min per IP. |

## Rules

1. Every requirement has ≥2 acceptance criteria.
2. Each criterion is independently testable (either a property-based test, a BDD scenario, or a direct unit test maps to it).
3. Responses must be measurable: numbers, specific status codes, named state transitions — never "as expected" or "correctly".
4. Triggers and states use present tense. Responses use `SHALL` (not "should", "must", "will").
5. No passive voice in responses — identify the system taking the action.

## Common mistakes

| Bad | Why | Fix |
|---|---|---|
| "WHEN user logs in, system works correctly" | "Correctly" is untestable | "WHEN user submits valid credentials, THE API SHALL return 200 with a JWT in an httpOnly cookie." |
| "The API should handle errors" | `should` is aspirational; "handle" is vague | "IF the database is unreachable, THEN THE API SHALL return 503 with retry-after header." |
| "THE system SHALL be fast" | Unquantified | "THE API SHALL respond within 200ms P95 on the /vendors endpoint." |

## Traceability

- Each acceptance criterion gets a stable ID: `R<N>.<M>` (requirement N, criterion M).
- Code referencing requirements uses an inline marker: `# R2.1:` or `// R2.1:`.
- Tests assert requirement IDs in docstrings: `"""R2.1: search scores bounded [0,1]."""`.

## Migration provenance

Extracted from `.kiro-archive/steering/spec-creation-guide.md` (2026-05, 1511 lines). Only the EARS + traceability sections migrated; rest was Kiro-workflow-specific.
