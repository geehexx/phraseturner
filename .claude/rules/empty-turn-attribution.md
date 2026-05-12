---
name: Empty-turn attribution — what counts as a user message
description: Hook responses, system reminders, background notifications, and task-completion events are NOT user messages. A bare "Continue" IS a user message (user confirmed they never type it alone). Do not fabricate user attribution for empty turns.
type: rule
---

# Empty-turn attribution

A message arriving in the conversation is a **user message** only when it
contains explicit text from the human. Everything else — even if it
appears at a `user`-role turn — is infrastructure, not instruction.

## The rule

| Source of turn | Is it a user message? | How to treat it |
|---|---|---|
| Human typed text in the prompt box | Yes | Genuine instruction; enrich, clarify, execute |
| Bare single word (e.g. "Continue", "Yes", "Go") | Yes | Genuine instruction (the user confirmed they never type these alone — so when you see one, it IS real) |
| `<system-reminder>` tag content | No | System-level instruction; follow it, don't attribute to user |
| `<task-notification>` block from async agent | No | Background event; acknowledge internally; do NOT treat as user approval |
| UserPromptSubmit hook enrichment (`additionalContext`) | No | Additional context; never a command |
| Empty turn body | No | Vacuous — do not fabricate "The user said 'Continue'" |
| Tool results the system replays after compaction | No | Internal plumbing |

**Why**: The user has flagged this pattern repeatedly (`lessons-inbox/2026-05.md:285-319, 411-432`). Fabricating user attribution on empty / hook / notification turns leads to one of two failure modes:

1. **HITL violation** — continuing past a blocking question because a background-task notification arrived during the wait.
2. **Ghost-instruction** — writing that "the user said X" when no such text exists, then using that fabrication as a justification in later reasoning.

Prior investigation confirmed hook handlers do NOT emit "Continue" / "genuine user" text; the attribution is model-side. This rule is the model-side fix.

## How to apply

**Before acting on any turn**, ask:
1. Did the human type text in this turn? If yes — genuine user message.
2. If the turn body is empty or contains only `<system-reminder>` / `<task-notification>` / infrastructure markers — do NOT say "the user said X". Do NOT treat it as approval for a previously-asked blocking question. Continue the prior work silently, or wait if a blocking question is outstanding.
3. A bare `Continue` by itself IS a user message — act on it.

**After asking a blocking question** (explicit HITL gate, destructive action, architectural fork), end the turn. Any non-human turn that arrives next is noise, not consent. Only explicit user text after the question counts as approval.

**When summarising session history**, never quote or paraphrase a "user said" line that came from an empty or infrastructure turn. If memory is unclear, check the actual transcript before quoting.

## What infrastructure turns look like

These are not exhaustive but cover the common shapes you'll see. If the entire turn body matches one of these patterns (optionally plus the `<local-command-*>` / `<command-*>` wrapper for slash commands), it is NOT a user message.

| Pattern | Example opening | Source |
|---|---|---|
| `<system-reminder>` | `<system-reminder>\nThe task tools haven't been used recently.` | Claude Code harness — budget / tool nudges |
| `<system-reminder>` with prompt eval | `UserPromptSubmit hook additional context: PROMPT EVALUATION` | `prompt-improver` plugin hook |
| `<task-notification>` inside `<system-reminder>` | `[SYSTEM NOTIFICATION - NOT USER INPUT]\n<task-notification>` | Async agent completion event |
| `<local-command-stdout>` following a `<command-name>` tag | `<command-name>/model</command-name>` | User ran a slash command; treat the stdout as informational, not as a request to act further |
| `<new-diagnostics>` inside `<system-reminder>` | `PostToolUse:Write hook additional context: ⚠️ Ruff violations` | Linter / type-checker hook |
| Empty body | No text content at all | Typically the tail of a tool-result turn, or a race between notification and next prompt |

If the turn contains **any** text that is visibly typed by the human — even a single word like "Continue" or "go" — it is a genuine user message. The tests above apply only when the turn is EXCLUSIVELY infrastructure content.

## Anti-patterns

- ❌ "The user said 'Continue' — proceeding with Option A" after empty turn following a yes/no question
- ❌ "Based on the user's confirmation, I will…" when the prior turn was a task-notification
- ❌ Fabricating paraphrased user text to bridge reasoning steps ("the user wants this shipped")
- ✅ "Continuing the prior task" with no attribution, when the turn is genuinely empty
- ✅ "Waiting for user response on the blocking question above" when a notification arrives mid-wait

## Signal this is happening to you

You're about to write "The user said…" or "The user wants…" — stop and check whether the nearest `user`-role turn contains actual typed text. If it doesn't, rewrite without the attribution.
