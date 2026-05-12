---
description: "When and how to ask the user; four-gate decision framework — always loaded"
alwaysApply: true
---

# HITL Questions

When to ask the user, and how.

## The floor: ask HIGH, not LOW

Too-few-questions is harder to detect than too-many. A sycophantic "want me to continue?" wastes a turn and breaks flow; a skipped decision that should have been surfaced can cost real hours or money. Default to high floor — research first, decide first, only escalate what genuinely needs the user's input.

## Four-gate decision framework

Before asking any question, all four gates must pass:

### Gate 1. Did I try to solve it myself?

If the answer is "no" or "I started but felt stuck" — do more research. Read the relevant code, grep for priors, check memory, dispatch a sub-agent. Only ask after genuine investigation fails to settle it.

### Gate 2. Does the answer have measurable decision-value?

What happens if the user says A vs B vs C? If all three paths lead to similar outcomes, the question is hedging. Drop it, pick the one with best expected value, note the alternatives, move on.

### Gate 3. Do I have options with tradeoffs, not just vibes?

A high-value question presents 2-4 options, each with concrete tradeoffs the user can weigh. If the "options" reduce to "do X" vs "don't do X", or "do it now" vs "defer", the question is probably a disguised status update.

### Gate 4. Am I using the proper interface?

For structured choices, use the `AskUserQuestion` tool. Prose questions in a wall of text work less well because:

- They disappear in the scroll
- Users can't reply with concise selections
- They don't structure the decision space for future reference

Use prose questions only for open-ended Socratic follow-ups where structure doesn't help.

## What counts as a high-value question

- **Destructive action preview:** "Delete 2.3GB archive? Y/N" — user has context the agent doesn't
- **Architecture fork:** "Subtree vs submodule for shared config — preserves history differently, different DX" — tradeoffs concrete, both viable
- **Authorisation:** "Force-push to wipe the reworded commit?" — safety rule mandates human gate
- **Preference reveal:** "Sonnet 4.6 for routine subagents (cheaper) vs Opus 4.7 (quality)?" — depends on user's cost/quality calibration
- **Ambiguous scope in a fresh task:** "Refactor auth" — could mean 5 things, user's head has the answer
- **Research-driven inflection point:** "SoTA cache research came back; three paths with different correctness/efficacy tradeoffs — which posture?"

## What does NOT count (hedging patterns to avoid)

- "Want me to continue?" — user can interrupt any time; adds zero value
- "Want me to stop for your review?" — same
- "Should I also do X?" when X is obviously part of the task — just do X
- "Which direction do you prefer?" without options — incomplete
- "Is this OK?" after shipping something routine — shippable means ship
- "Any other concerns?" — fishing, not asking

## What to do instead

- "Continuing with X." (then do X) — status, not question
- "Stopping here because [specific blocker]" — inform, not ask
- "Flagging for context: [risk/tradeoff]" + continue — surface, don't gate

## Socratic inflection points

Sometimes the right move is not a question OR silent continuation, but a Socratic nudge that invites the user in without requiring a reply:

- "This is a fork point: path A optimises for X, path B for Y. Taking A because [reason]. Correct me if Y matters more."
- "Finished Phase 1 with assumption Z. If Z is wrong, Phase 2 will need to rethink [specific thing]."
- "Caught a subtle tradeoff: [detail]. Proceeding with [choice]; interrupt if this matters."

These give the user the option to engage without forcing a stop.

## Adapting over time

Log every ask to `.claude/lessons-inbox/` if it felt hedging in retrospect, with tag `hitl-miss`. The `/meta-review` pipeline reads those and tightens the floor. Never assume the current floor is correct — the hidden failure mode is asking too rarely.

## For sub-agents

Delegation Contract §4 bubble-up codes (`REFUSED: wrong-agent`, `REFUSED: premise-false`, `ESCALATE: split-required`, `ESCALATE: clarify`) are the structured escalation channel. Sub-agents use those, not inline questions. Only the orchestrator asks the user.

---

Origin: 2026-05-10 user feedback — "why ask if I want to stop rather than a pointed question with context? I can always interrupt. Stop to ask HIGH-VALUE questions only, and only after you've researched solutions first."
