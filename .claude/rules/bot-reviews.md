---
description: "How to discover and resolve bot review comments (CodeRabbit, Qodo, Copilot review, others) on any PR we don't own, including per-bot tooling and a 'done criteria' checklist before marking work finished."
globs: [".github/**", ".claude/rules/**"]
alwaysApply: false
---

# Bot Review Workflow — Cross-Project

We open PRs against repos with different bot configurations. CodeRabbit is
common; Qodo, Greptile, Codium, Diffblue,
GitHub Copilot code review are plausible. "PR is done" means BOTH: status
checks pass AND all bot inline comments are either resolved or intentionally
dismissed with a comment-reply rationale. Status-check-pass alone is not
sufficient — most bots post comments without failing the check.

## Discovery — always run these three API calls before assuming a PR is done

On any PR (ours or a fork/upstream), run:

```bash
# 1. Inline review comments (path+line attached) — the actionable ones
gh api /repos/{owner}/{repo}/pulls/{pr}/comments \
  --paginate \
  --jq '.[] | {user: .user.login, path: .path, line: .line, body: .body[:400]}'

# 2. Issue-level comments (walkthroughs, summaries, bot-kickoff threads)
gh api /repos/{owner}/{repo}/issues/{pr}/comments \
  --paginate \
  --jq '.[] | {user: .user.login, body: .body[:400]}'

# 3. Reviews (APPROVED / CHANGES_REQUESTED / COMMENTED from humans + bots)
gh pr view {pr} --repo {owner}/{repo} \
  --json reviews,reviewRequests,reviewDecision,mergeStateStatus
```

Count of comments tagged `[bot]` in user.login minus resolved = backlog.
A PR with 23 unresolved bot comments and no human review is NOT done.

## Common bot users to look for

| user.login | Bot | Where configured |
|------------|-----|------------------|
| `coderabbitai[bot]` | CodeRabbit | `.coderabbit.yaml` at repo root |
| `qodo-code-review[bot]` | Qodo | Qodo dashboard (not in-repo) |
| `greptile-apps[bot]` | Greptile | Greptile dashboard |
| `github-actions[bot]` | Copilot code review or custom action | `.github/workflows/` |
| `codium-ai[bot]` | Codium | Codium dashboard |
| `deepsource[bot]` | DeepSource | `.deepsource.toml` |

If the PR target repo uses a bot we haven't seen, read the bot's most
recent comment for a link to its docs — bots typically self-advertise.

## Severity taxonomies differ between bots — normalise before triaging

CodeRabbit: Blocking / Suggestion / Nitpick / Praise.
Qodo: Bug / Rule violation / (sometimes) Test suggestion. Severity via
  icons: 🔴 Critical / 🟠 Major / 🟡 Minor / 🔵 Trivial.
Greptile: Major / Minor / Nit.

Map to our internal three-bucket scheme before working:

| Our bucket | Action | Examples |
|------------|--------|----------|
| **Must-fix** | Code change required before merge | Security boundary, correctness bug, resource leak, concurrency regression |
| **Should-fix** | Fix unless resource-bound; explain if skipped | Performance nit, API ergonomics, deprecated pattern |
| **Intentional** | Reply-and-resolve with rationale | Deferred feature, style disagreement, rule mismatch with our conventions |

## Resolving comments — three valid outcomes, each needs a trace

1. **Fix and push** — commit message references the comment. The bot
   re-reviews on push and marks resolved automatically (usually).
2. **Disagree and reply** — use `@coderabbitai resolve` (CodeRabbit) or
   post a reply explaining the disagreement. For Qodo, click "resolve"
   in the UI or reply on the thread. Do NOT just ignore — unresolved
   threads block merge on repos that require review resolution.
3. **Defer to a follow-up ticket** — open a Linear (or repo issue)
   tracking the deferred item, reply with the ticket link, then resolve.

## Done criteria before `gh pr merge`

For any PR (ours OR an upstream/fork PR we want to move to ready):

- [ ] All inline bot comments at Critical/Major severity are fixed OR
      have a reply-and-resolve rationale attached.
- [ ] All bot-reported bugs (regardless of severity) are fixed OR have
      a follow-up ticket linked.
- [ ] CI checks green (including any CodeRabbit / Qodo aggregate check).
- [ ] No open `CHANGES_REQUESTED` reviews from humans.
- [ ] `gh pr view --json mergeable,mergeStateStatus` returns MERGEABLE
      and either CLEAN or BLOCKED only due to review-count gates we
      intend to satisfy next.

If any box unticked: PR is NOT done. Report to user with the list of
open items, don't merge.

## We don't own the target repo — read-only constraints

When contributing to forks/upstream:
- CANNOT change `.coderabbit.yaml` or Qodo config — respect whatever
  conventions are configured.
- CAN reply to bot comments in PR review threads.
- CAN use `@coderabbitai resolve` even on a fork PR if CodeRabbit is
  installed on the source repo.
- For Qodo in a repo where we don't have a Qodo account, we cannot
  reply via the Qodo dashboard but we CAN reply as a normal GitHub
  comment — Qodo's bot reads replies.

## Tooling setup

- `gh` CLI: already installed; authenticated via `gh auth status`.
- CodeRabbit CLI (`coderabbit review`): good pre-push check for repos
  where CodeRabbit is set up. Not needed for fork/upstream PRs where we
  rely on the server bot.
- Qodo CLI: not installed by default. Don't install unless a user need
  emerges — per user direction "no MCPs or anything heavy just for this".
- Browser access via playwright MCP: useful only if the bot UI has
  richer context than the API. API is almost always sufficient.

## When to save bot findings to a plan file

If the PR has more than ~10 bot comments AND the PR is going to be
idle overnight (waiting on deploy, user review, etc.), write a plan
file at `docs/plans/<date>-<repo>-pr<N>-bot-review-triage.md`
with the full findings + severity categorisation + recommended fix
sequence. The session that resumes the PR loads that file; re-fetching
from the API is cheaper but loses the prior triage judgements.

## Anti-patterns

- Merging because "CI is green" without checking inline comments.
- Addressing comments one at a time without first categorising —
  leads to rework when a batch of nits can be one commit.
- Silently resolving a bot thread without a reply — the user reviewing
  later can't tell if we considered it or missed it.
- Using `--admin` merge to bypass branch protection when bot comments
  are unaddressed — that's the exact scenario branch protection is
  designed to catch.
