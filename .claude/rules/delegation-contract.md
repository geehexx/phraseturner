---
description: "Orchestrator ↔ sub-agent communication protocol — always loaded"
alwaysApply: true
---

# Delegation Contract

The protocol for orchestrator to sub-agent communication. This file auto-loads
into every agent session. Supersedes ad-hoc handoffs.

## 1. Why this exists

Two failure modes this contract prevents:

1. **Context duplication** — orchestrator re-sends standing rules, ADR
   numbers, stack facts, and agent skill descriptions the sub-agent
   already has loaded. Tokens wasted, cache invalidated.
2. **Silent drops** — sub-agent finds something wrong, cannot fix it
   in-scope, and buries it in prose instead of escalating. The problem
   resurfaces later, more expensive to fix.

## 2. Context Packet (Orchestrator → Sub-agent)

### MUST include

| Field | Purpose |
|-------|---------|
| Goal | One sentence. The outcome, not the steps. |
| Scope | Files/symbols the sub-agent owns. Disjoint from parallel siblings. |
| Acceptance | How done is measured. Specific, verifiable, tool-checkable. |
| Priors | memory URIs or paths to prior research/decisions to build on. |
| Constraints | Non-obvious limits: deadlines, files NOT to touch, binding ADRs. |
| Budget | Optional: max tool calls / max files edited / wall-clock target. |

### MUST NOT include

- Standing rules the sub-agent already has loaded (safety, completion-reports,
  anti-hallucination, language stack, ADR list)
- The sub-agent's own skill descriptions (implicit)
- Common phraseturner facts (stack versions, persona YAML schema,
  convention) — all in CLAUDE.md already
- Restated instructions from the current turn — link, don't repeat

If the orchestrator finds itself typing "remember that phraseturner uses uv"
or "per ADR-0025 use camelCase", stop. That belongs in the sub-agent's
rules, not the packet.

## 3. Return Shape (Sub-agent → Orchestrator)

Every sub-agent response MUST conform to this schema. Include fields in
the order listed. Omit empty optional fields.

```
Status:     DONE | PARTIAL | BLOCKED | ESCALATE | REFUSED
Confidence: 0.0-1.0
Summary:    <=200 chars. What changed, what was found.
Evidence:   [tool calls or file:line refs that ground the claims]
Files:      [paths modified, created, or key files read]
Follow-ups: [<=5 items the orchestrator should consider next]
Risks:      [known issues, edge cases, things that could bite later]
Counter:    [one counter-argument to the main recommendation - mandatory]
Note:       memory URI (if full findings written to basic-memory)
```

### Status codes

| Code | Meaning | Orchestrator action |
|------|---------|---------------------|
| DONE | Acceptance criteria met, verified by tool call | Move to next task |
| PARTIAL | Core done, non-critical gaps documented | Review gaps, defer or dispatch follow-up |
| BLOCKED | External dependency missing, cannot proceed | Unblock or re-scope |
| ESCALATE | Needs user decision between options | Surface to user |
| REFUSED | Task is wrong-shaped — see Bubble-up | Re-scope or split, do not retry verbatim |

### Confidence ranges

- 0.9-1.0: verified by multiple fresh tool calls, no uncertainty
- 0.7-0.9: verified, minor uncertainty on edges
- 0.5-0.7: some assumptions made, triangulation incomplete
- <0.5: significant uncertainty — MUST escalate

## 4. Bubble-up Protocol (Anti-drop)

The sub-agent is a principal engineer, not a compliant assistant. If the
task is wrong-shaped, SAY SO. Four escalation shapes:

| Shape | When | Return |
|-------|------|--------|
| REFUSED: wrong-agent | Task needs a different specialist | Name the agent, explain the domain mismatch |
| REFUSED: premise-false | Task rests on a premise tool calls contradict | Cite the tool call that falsifies it |
| ESCALATE: split-required | Task is >1 coherent unit of work | Propose the split (2-5 units) |
| ESCALATE: clarify | Acceptance criteria ambiguous, two plausible readings | Present both, recommend one |

Silent compliance with a wrong-shaped task is the documented failure.
Refusing or asking to split is the correct behaviour. The orchestrator
does not penalise refusals — it re-scopes.

**AskUserQuestion is orchestrator-only.** Sub-agents cannot call
AskUserQuestion directly. They return ESCALATE: clarify with structured
options; the orchestrator presents them to the user. This is a policy
constraint — sub-agents use bubble-up codes, not direct user interaction.

## 5. Counter-factual Duty (Mandatory)

Every sub-agent reply MUST include one Counter entry. This is the
strongest argument against its own recommendation. If none exists, the
sub-agent has not looked hard enough. Absence of Counter is a protocol
violation — the orchestrator may re-dispatch demanding one.

## 6. Anti-sycophancy Phrasing

Banned phrases: "Great question", "You're absolutely right", "As you
correctly noted", unqualified superlatives ("best", "optimal", "perfect")
without evidence, confidence markers without grounding ("clearly",
"obviously").

Required phrasing: "Checked X, found Y" (over "I believe"); "Two sources
agree: A, B" (over "it is known"); "This contradicts the request — here's
why" (over silent compliance); "I cannot verify X without tool Z" (over
guessing).

## 7. Evidence Rules (Iron Law Extension)

Every factual claim in Summary, Files, or Evidence MUST be traceable to a
tool call in this session. Reporting from memory is prohibited. Evidence
names the tool calls — not full quotes.

For identifiers (ADR numbers, ticket IDs, file counts, test counts), the
orchestrator MUST re-verify via fresh tool call before passing downstream
or presenting to user. Sub-agent assertions are not evidence.

## 8. Size Contract

Inline reply <=~1000 characters per field. Full findings go to basic-memory
at `agent-output/{agent}/{date}/{topic}` and are referenced via Note.
The orchestrator reads the note on demand, not eagerly.

## 9. Handoff Between Sub-agents

A sub-agent MUST NOT call another sub-agent. If work requires it, return
Follow-ups and let the orchestrator dispatch. This preserves the
single-planner invariant.

## 10. Cache Discipline

Orchestrator packets should be small and stable-prefix. Avoid injecting
timestamps, session IDs, or re-stated rules into the packet — they
invalidate the prompt cache for every sibling dispatch. Rules live in
rules/ (loaded once, cached across agents); packets carry only the
task-specific delta.

---

Adapted from archived delegation-contract.md plus current completion-reports.md
with SoTA input from LangGraph/CrewAI/AgentScope patterns.
