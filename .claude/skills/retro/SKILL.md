---
name: retro
description: "Sprint or session retrospective workflow with structured output. Use after completing a spec phase, sprint, or significant piece of work to capture what worked, what didn't, and what to improve. Produces a structured retrospective note in basic-memory that feeds into the Five-Gate lesson governance pipeline. Grounds findings in git history and tasks.md evidence rather than memory. Identifies steering improvement flags and process improvement targets for future sessions. Integrates with the ralph-loop agentStop hook for session reflection. Activates on: retrospective, retro, sprint retro, session retrospective, lessons learned, what went well, what didn't work, post-mortem, after action review, phase retrospective, session reflection, capture lessons."
metadata:
  category: planning
  complexity: 2
  activation_examples:
    - "retro on the Phase 3 steering token reduction work"
    - "sprint retrospective after the demo-ready phase"
    - "what went well and what didn't in the WSL migration?"
    - "lessons learned from the ElastiCache Redis implementation"
    - "session retrospective — capture what we learned today"
  related_steering:
    - tool-selection
    - spec-execution-guide
---

# Retro Skill

Structured sprint or session retrospective workflow. Adapted from garrytan/gstack (MIT). Use after completing a spec phase, sprint, or significant piece of work to capture institutional knowledge before it fades.

## When to Activate

- After completing a spec phase (e.g., Phase 2 of platform-hardening)
- After a sprint or demo milestone
- After a significant technical decision or migration
- After a session where something went unexpectedly well or badly
- When the ralph-loop agentStop hook fires and prompts for reflection
- Before archiving a spec — capture lessons before the context is gone

## Step 1: Gather Context

Load the relevant spec and recent git history to ground the retrospective in evidence, not memory.

```python
# Read the spec tasks to see what was completed
Read (multiple)([
    ".claude/specs/{spec-name}/tasks.md",
    ".claude/specs/{spec-name}/requirements.md",
])

# Check recent commits for evidence of what was done
Bash(command="git log --oneline --since='7 days ago' -- backend/ frontend/ .claude/")

# Check basic-memory for prior retro notes on this spec
mcp_basic_memory_search_notes(query="{spec-name} retrospective lessons")

# Check for any feed-forward queue items from the session
mcp_basic_memory_search_notes(query="{spec-name} feed-forward")
```

Parse `tasks.md` to identify:
- Tasks completed `[x]` — what was delivered
- Tasks still pending `[ ]` — what was deferred and why
- Tasks in-progress `[-]` — what was interrupted

## Step 2: What Went Well

Identify 3–5 specific things that worked, grounded in evidence from the work. Avoid vague praise — cite specific decisions, tools, or patterns.

**Evidence sources**:
- Tasks completed ahead of schedule
- Sub-agent calls that returned DONE with confidence ≥ 0.9
- Patterns that were reused from prior work (basic-memory hits)
- ADR decisions that proved correct in practice
- Tool choices that saved time (e.g., `Bash` (grep/rg) finding a pattern quickly)

**cv-builder-specific signals to look for**:
- Did the Five-Gate validation catch issues early?
- Did the ralph-loop session reflection surface useful insights?
- Did basic-memory prior knowledge prevent re-research?
- Did the planner DAG hold up without JIT re-planning?
- Did the context-router correctly activate steering on the first try?

**Format**:
```
✅ What Went Well:
1. {specific thing} — evidence: {git commit / task / tool call}
2. {specific thing} — evidence: {what confirmed it worked}
3. {specific thing} — evidence: {measurable outcome}
```

## Step 3: What Didn't Work

Identify 3–5 specific things that failed or were harder than expected. Be precise — vague complaints don't produce actionable improvements.

**Evidence sources**:
- Tasks that required multiple attempts or JIT re-planning
- Sub-agent calls that returned BLOCKED or ESCALATE
- Tool failures or MCP connectivity issues
- ADR violations discovered during code review
- Assumptions in the spec that turned out to be wrong
- Context overflow or context pressure events

**cv-builder-specific failure patterns to check**:
- Did any async safety violations (ADR-0006) slip through to code review?
- Did any `BaseModel` instead of `BaseSettings` bugs appear?
- Did any M2M queries miss `.distinct()`?
- Did the spec have stale assumptions about the codebase?
- Did any hook fire unexpectedly or fail silently?
- Did any sub-agent produce low-confidence output that required re-work?

**Format**:
```
❌ What Didn't Work:
1. {specific thing} — evidence: {error / blocked task / re-work required}
2. {specific thing} — evidence: {what went wrong}
3. {specific thing} — evidence: {cost: time / quality / rework}
```

## Step 4: What to Improve

Identify 3–5 actionable improvements for next time. Each improvement must be specific enough to act on — not "communicate better" but "add a premise check step before starting Phase 2 implementation".

**Improvement categories**:
- **Spec quality**: Were requirements ambiguous? Add a premise check step.
- **Tooling**: Was a tool missing or slow? Propose an enhancement.
- **Steering**: Was a steering file missing guidance that would have helped? Flag for enrichment.
- **Agent routing**: Was the wrong agent used? Update the routing table.
- **Process**: Was a step skipped that caused rework? Make it mandatory.

**cv-builder-specific improvement targets**:
- If async violations appeared: add `verifai-async-audit` skill to pre-phase checklist
- If spec premises were wrong: add `verifai-spec-premise-check` skill to pre-implementation
- If basic-memory wasn't searched first: reinforce tool-selection §10 memory write-back
- If a steering file was missing: flag for token enrichment (target ≥1,000 tokens, ideally 2,000+)
- If a hook misfired: document in basic-memory under `meta-lessons/hook-issues`

**Format**:
```
🔧 What to Improve:
1. {specific improvement} — owner: {steering file / agent / process step}
2. {specific improvement} — owner: {what needs to change}
3. {specific improvement} — owner: {who/what implements this}
```

## Step 5: Capture in basic-memory

Write the retrospective to basic-memory so it feeds into the Five-Gate lesson governance pipeline.

```python
# Get current date for the note title
Bash (date)()

# Write the retrospective note
mcp_basic_memory_write_note(
    title="{spec-name}-retro-{date}",
    directory="meta-lessons",
    content="""
## What Went Well
{3-5 items from Step 2}

## What Didn't Work
{3-5 items from Step 3}

## What to Improve
{3-5 items from Step 4}

## Steering Improvement Flags
{list any steering files that need enrichment}

## Process Improvement Flags
{list any process steps that should be added or changed}

## Relations
- relates-to [[{spec-name}]]
- implements [[ralph-loop-reflection]]
"""
)
```

**Observation taxonomy** — use these tags in the note content:
- `[decision]` — a decision that proved correct or incorrect
- `[finding]` — something discovered during the work
- `[pattern]` — a reusable pattern that emerged
- `[workaround]` — a workaround applied and why
- `[limitation]` — a tool or process limitation encountered

## cv-builder-Specific Patterns

### ralph-loop Integration

The `ralph-loop` hook fires on `agentStop` and prompts for session reflection. The retro skill is the structured version of that reflection — use it when the ralph-loop prompt fires at the end of a significant session.

The ralph-loop output feeds into the same `meta-lessons/` directory in basic-memory. Cross-reference the retro note with any ralph-loop notes from the same session.

### Five-Gate Lesson Governance

Retrospective notes in `meta-lessons/` are processed by the Five-Gate validation pipeline:
1. **Gate 1**: Is the lesson specific enough to act on?
2. **Gate 2**: Does it reference a specific steering file or process step?
3. **Gate 3**: Is it grounded in evidence (not just opinion)?
4. **Gate 4**: Does it avoid duplicating existing guidance?
5. **Gate 5**: Is it actionable within the current sprint?

Lessons that pass all five gates are candidates for steering file enrichment. Flag them explicitly in the note.

### Steering Improvement Flags

When a retro reveals that a steering file was missing guidance, add a flag:

```python
mcp_basic_memory_edit_note(
    identifier="{spec-name}-retro-{date}",
    operation="append",
    content="""
## Steering Improvement Flags
- `django-patterns.md`: missing guidance on sync_to_async batch pattern for N+1 prevention
- `testing-standards.md`: missing example of testcontainer session-scope fixture
"""
)
```

These flags are reviewed during the next kiro-meta session and converted into steering enrichment tasks.

### Retro Output Format

The final retro note should be 400–800 words. Longer notes lose focus; shorter notes lack evidence. If the retro is for a multi-phase spec, write one note per phase rather than one giant note.

**Anti-patterns**:
- ❌ "Everything went well" — not grounded in evidence
- ❌ "We should communicate better" — not actionable
- ❌ Retro written from memory without reading tasks.md or git log
- ❌ Retro that doesn't reference any specific tool calls or decisions
- ✅ "The planner DAG held up for 8/10 tasks — JIT re-planning was only needed when the ElastiCache connection string format changed (evidence: task 3.4 BLOCKED → re-planned)"
