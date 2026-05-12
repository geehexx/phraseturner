# Repo Scope

phraseturner is a single-repo project — all product code, tests, specs, docs, Claude Code config live in `geehexx/phraseturner`.

## Routing table

| Topic | Path |
|---|---|
| Product code | `src/phraseturner/` |
| Tests | `tests/` (unit, integration, properties, calibration) |
| Claude Code config | `.claude/` + `CLAUDE.md` + `.mcp.json` |
| Specs | `.kiro/specs/` (legacy, reference only during migration) |
| Decisions | basic-memory `decisions/{YYYY-MM-DD}-{slug}` |
| Plans | `docs/plans/` for active work (not gitignored) |

## Migration state

- Legacy `.kiro/` directory remains as reference during migration. Do NOT edit `.kiro/*` — treat it read-only.
- New work goes in `.claude/` and the top-level `CLAUDE.md` / `.mcp.json`.
- Cleanup of `.kiro/` happens as a user-approved separate commit at end of migration.

## What does NOT belong in this repo

- kiro-gateway (shared tooling, separate repo `geehexx/kiro-gateway`)
- verifai-claude config (different project)
- cv-builder config (different project — different stack, personas, scoring rubric)

## Sharing with other projects

phraseturner, cv-builder, VerifAI all share:
- `kiro-gateway` (running locally on `127.0.0.1:8765`) — gateway auth/token shared across projects
- `basic-memory` MCP server — each project has its own `basic-memory` project entry; notes don't cross-contaminate
- Global skills/agents from `~/.claude/plugins/cache/`

NOT shared: local skills/rules/agents. Each project has its own `.claude/` with project-specific content.
