# Plan Mode

Claude Code's Plan Mode is a permission posture, not a workflow. It restricts Claude to read-only exploration — reads and shell commands are free, writes still prompt. Exit via `ExitPlanMode` (which presents the plan for approval) or `Shift+Tab`.

## When to enter plan mode

- PR-level or multi-file work (touching 3+ files, cross-domain changes)
- Schema changes, new library integration, architectural decisions
- Anything described as "feature" or "refactor" rather than "fix"
- When the user asks a question like "how should we approach X?"

Open the planning turn with: **"What clarifying questions do you have?"** (Reddit-validated pattern — the plan turn is also a clarification turn).

## When to skip plan mode

- Trivial single-file changes, typos, obvious bug fixes
- When the user provides a tight, unambiguous instruction with clear file paths
- Follow-up edits during an already-approved plan execution
- When you already have a plan in context and the request is to execute it

Plan mode amplifies good context; it does NOT compensate for weak context. If CLAUDE.md / AGENTS.md is weak, plan mode produces worse plans, not better.

## Entry points

- Native `/plan <feature>` — Anthropic's built-in (replaces our old `/plan` wrapper)
- `Shift+Tab` — cycles `default → acceptEdits → plan`
- `claude --permission-mode plan` — start the session in plan mode
- `EnterPlanMode` tool — invokable mid-session (main agent; sub-agent inheritance is undocumented)

## Exit and approval

`ExitPlanMode` presents the plan for approval. Approval menu:
- Start in auto mode, accept-edits, review each, keep planning, refine with Ultraplan

After approval, sub-agents spawned from that session are NOT guaranteed to inherit plan mode (Anthropic docs explicitly state auto-mode subagent `permissionMode` frontmatter is ignored; plan-mode propagation is undocumented). Treat sub-agents as running in default mode unless you pass `permissionMode` explicitly and verify.

## Plan persistence (Level 3+ work)

An approved plan for a Level 3+ task MUST land in a durable place:

- **Work-in-progress on a ticket**: write the plan to the Linear ticket description (create the ticket first if absent)
- **Research/direction without an immediate ticket**: write the plan to basic-memory at `decisions/{YYYY-MM-DD}-{slug}`

Level 1-2 plans (trivial, single-file) are ephemeral — no persistence required. This policy stops approved plans decaying into session-only artefacts where the commit message is the only trace.

## Not to do

- Don't enter plan mode for trivial edits — adds a turn with zero decision value
- Don't approve a plan without reading it — community anti-pattern #2 (`u/WireDogTech`: "you may tell you the plan and it may be clear as day wrong and you won't figure it out till it's too late")
- Don't let a plan drift silently during execution — if the plan changes materially, re-enter plan mode or update the persisted copy
- Don't dispatch `planner` sub-agent AND use plan mode on the same level-3+ task — double-counts work. See `planner.md` §Plan mode interaction.
- Don't use plan mode as a substitute for a solid CLAUDE.md — fix the context, not the ceremony
- **Don't commit to a cache keying design without a correctness review.** Before implementing any cache, dispatch a correctness-focused sub-agent to verify the keying logic: two requests with the same key must always be semantically equivalent. Prefix-only keying for full-response caches is a known failure mode — different trailing turns collide and return wrong answers. The property test `cached_response(key) == response(same_key_different_trailing_turn)` must fail on the broken design before you ship.

## Related

- `.claude/skills/feature-planning/SKILL.md` — premise challenge + scope modes, orthogonal to plan mode
- `.claude/agents/planner.md` — work breakdown structure (DAG + agent assignment), distinct from plan mode's "propose approach"
- `.claude/skills/plan-{ceo,eng,design}-review/SKILL.md` — post-plan review skills; invoke after `ExitPlanMode` presents a plan, before approval
