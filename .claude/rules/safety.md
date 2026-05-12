# Safety Rules

## Three-Tier Action Boundaries

**Always safe** (proceed without asking):
- Read files, run diagnostics, search codebase
- Run tests, create new files in appropriate locations
- Query local caches (LanceDB read-only)

**Ask first** (explain what you're doing):
- Delete files, modify shared configuration
- Update dependencies (uv add / remove)
- Modify CI/CD pipelines

**Never do** (hard stops):
- Commit to main directly
- Push to remote without user approval
- Modify `.env` or commit secrets
- Remove existing tests without replacement
- Trigger Nova Act on LinkedIn without HITL approval
- Merge PRs (user decides)

## Nova Act / Scraping Protection (CRITICAL)

Nova Act scraping costs real money (StarburstBackend paid tier) and LinkedIn actively throttles automated access.

Before triggering ANY `nova_act.NovaAct.act()` call against linkedin.com:
1. Verify `LINKEDIN_SCRAPE_APPROVED=1` is set, OR the user explicitly typed "yes scrape".
2. Warn that cost is per-invocation and LinkedIn may lock the account.
3. If 2+ consecutive Nova Act calls have failed, STOP and escalate.

Preferred order for LinkedIn data:
1. Cached data in `data/linkedin_profile.yaml` (manual export)
2. `linkedin_scraper.py` read-only (no writes)
3. Nova Act scrape (LAST RESORT, explicit approval)

## Pre-commit Bypass — STRICTLY PROHIBITED

NEVER bypass pre-commit hooks (`SKIP=hook_name`, `--no-verify`, any other mechanism). If a hook fails: read the error, fix the root cause, re-run the hook, then commit.

## No AI Attribution in User-Facing Documents

NEVER mention Claude/AI as author/contributor in:
- Git commit messages
- PR descriptions
- Code comments
- Resume/CV output content (obvious — defeats the point of authored CV)
- Documentation

## No Internal Tooling References in Git-Tracked Docs

Never commit: `memory://` URIs, `.kiro/` paths (the old config), MCP tool names as implementation detail, `sub-agent` / `fork` / hook references as implementation detail.

## 3-Fix Escalation Rule

If 3+ fix attempts fail on the same issue, STOP. Three failed fixes means root-cause analysis is wrong.

## Destructive Operations

Before any destructive operation, state: what the operation will do, what could go wrong, whether it is reversible. Ask for explicit confirmation.

## Secret Handling

Never echo secret values. Reference by key name only (`NOVA_ACT_API_KEY`, not the literal). `.env` and `.envrc` are gitignored. AWS credentials live in `~/.aws/credentials`.
