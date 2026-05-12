# Anti-Hallucination Rules

Always verify file metrics, code structure, and test results with tool calls.
Never report from memory — memory is stale.

## Tool-First Grounding

```
❌ "The file has 489 lines"
✅ "From Read on meta-prompt.md: 489 lines"

❌ "Tests are passing"
✅ "From Bash(pytest): 0 failures, 0 errors"
```

## Self-Verification Protocol

Before reporting any factual metric, ask these 4 questions:
1. Did I verify this with a tool call in the current conversation?
2. Is the tool output current (not from a previous turn that may be stale)?
3. Could the file have changed since I last read it?
4. Am I confusing this file with a similarly named one?

If any answer is "no" or "unsure" — re-read the file before reporting.

## Context Isolation

When working with multiple files, explicitly track which data came from which file. The most common hallucination is attributing data from one file to another.

```
❌ "The configuration shows..."  (which configuration?)
✅ "In .claude/agents/orchestrator.md, the model field is claude-opus-4.7"
```

Before reporting any metric from a multi-file session:
1. "Did I verify this with a tool call?" — If no, verify now
2. "Am I confusing this with data from another file?" — If uncertain, re-check
3. "Is this from the current state or a previous state?" — Files change between sessions

## Pre-Edit Ritual (Non-Trivial Changes)

Before modifying any non-trivial symbol:
1. **Find** — locate the definition (search/grep)
2. **Blast radius** — check all callers/references
3. **Read** — get full implementation context
4. **Edit** — make the change
5. **Verify** — check callers still work, run diagnostics

Never edit a symbol without understanding who depends on it.

## Shell Output Truncation Warning

When tool output is truncated (indicated by `...` or cut-off text), do NOT assume the truncated portion is fine. Either:
- Read the full output before drawing conclusions
- Use targeted searches to find the specific information needed

Truncated output is incomplete evidence — never base claims on it.

## Delegation Output Anti-Patterns

When delegating work or requesting information, NEVER ask for raw/verbatim output:

| ❌ Bad | ✅ Good |
|--------|---------|
| "Return ALL output verbatim" | "Return a structured summary of findings" |
| "Dump the raw shell output" | "Report: what you found, what matters, what's blocked" |
| "Include full file contents" | "Summarise the key sections relevant to X" |

Raw output floods context without adding signal. Always request structured summaries.

## Completion Claims

Before claiming any task is done:
1. IDENTIFY the verification command
2. RUN it
3. READ the full output
4. VERIFY it supports the claim
5. Only THEN claim completion

Red flags — if you catch yourself using "should", "probably", "seems to", "likely", "I believe" before running verification, STOP and run the check.
