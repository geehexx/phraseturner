# Completion Reports

Every significant task ends with a structured completion report.

## Iron Law

**NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.**

Confidence is not evidence. Memory is not evidence. Only fresh tool output is evidence.

Before claiming done:
1. IDENTIFY the verification command
2. RUN it
3. READ the full output
4. VERIFY it supports the claim
5. Only THEN claim completion

## Rationalisation Prevention

| Rationalisation | Required Action |
|----------------|-----------------|
| "Should work now" | RUN the verification |
| "I'm confident" | Confidence ≠ evidence. RUN it. |
| "I just fixed it" | VERIFY the fix with a tool call |
| "It's a simple change" | Simple changes still need verification |
| "The pattern is correct" | Patterns can have typos. VERIFY. |

### Red Flags

If you catch yourself using any of these words before running verification, STOP immediately and run the check:
- "should"
- "probably"
- "seems to"
- "likely"
- "I believe"

These are rationalisation markers — they indicate you are about to claim something without evidence.

## Format

```
Status: DONE | PARTIAL | BLOCKED | ESCALATE
Confidence: 0.0-1.0
Changes: [list of files modified with what changed]
Verified: [tool calls that confirmed completion]
Remaining: [any gaps or deferred items]
```

## Status Codes

- **DONE**: All acceptance criteria met, verified by tool calls
- **PARTIAL**: Core functionality works, some non-critical items deferred (document what and why)
- **BLOCKED**: Cannot proceed without external input (state exactly what is needed)
- **ESCALATE**: Requires user decision (present options, don't decide unilaterally)

## Confidence Ranges

- 0.9-1.0: Verified by multiple tool calls, no uncertainty
- 0.7-0.9: Verified by tool calls, minor uncertainty about edge cases
- 0.5-0.7: Partially verified, some assumptions made
- <0.5: Significant uncertainty — escalate to user

## Phase Completion Verification

When claiming a phase or milestone is complete:
1. **READ** the task list via tool call
2. **COUNT** task states: complete, not started, in-progress
3. **VERIFY** count matches expected total
4. **REPORT** with grounding: "Phase N complete: verified by reading tasks — N/N done, 0 pending"
5. **BLOCK** if any tasks are incomplete — do NOT claim phase complete

```
❌ "Phase 0 complete (20/20)" — ungrounded, violates Iron Law
✅ "Phase 0 complete: read tasks.md confirms 20/20 tasks done, 0 pending"
```
