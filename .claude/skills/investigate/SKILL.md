---
name: investigate
description: "Systematic root cause analysis using the Iron Law debugging methodology. Use when a bug has resisted 2+ fix attempts, when the root cause is unclear, or when a system is behaving unexpectedly. Follows evidence-based elimination to find the true root cause before attempting any fix. Particularly effective for cv-builder-specific failure patterns: SynchronousOnlyOperation errors, BaseModel vs BaseSettings config bugs, M2M duplicate results, SSR hydration mismatches, and stale lru_cache config. Produces a hypothesis-driven investigation with a 3-fix escalation rule. Activates on: investigate, debug deeply, root cause analysis, why is this happening, iron law debugging, systematic debugging, bug investigation, unexplained behaviour, intermittent failure, hypothesis testing, evidence-based debugging."
metadata:
  category: quality
  complexity: 3
  activation_examples:
    - "investigate why the search returns no results for some queries"
    - "root cause analysis — the enrichment pipeline fails intermittently"
    - "why is this happening? the comparison table shows undefined values"
    - "iron law debugging on the rate limiter — it's not working correctly"
    - "systematic investigation of the hydration mismatch in the search page"
  related_steering:
    - django-patterns
    - testing-standards
---

# Investigate Skill

Systematic root cause analysis using the Iron Law debugging methodology. Adapted from garrytan/gstack (MIT). Use when a bug has resisted 2+ fix attempts, when the root cause is unclear, or when a system is behaving unexpectedly.

## The Iron Law

> **Never fix a bug you don't understand. Fix the root cause, not the symptom.**

A symptom fix makes the bug invisible without making it gone. The next developer (or the next deploy) will encounter the same root cause in a different form. Evidence-based elimination is slower than guessing, but it produces permanent fixes.

## When to Activate

- After 2+ failed fix attempts on the same bug
- When the root cause is genuinely unclear (not just "I haven't looked yet")
- When a bug is intermittent or environment-dependent
- When a fix in one place causes a regression somewhere else
- When the error message doesn't match your mental model of the code
- When a bug appears in production but not in development

## Step 1: Reproduce the Bug

Get a minimal, reliable reproduction before doing anything else. You cannot investigate a bug you cannot reproduce.

### Reproduction Checklist

```
What exact inputs trigger the bug?
  Input: {exact values, not "some queries" or "sometimes"}

What is the expected behaviour?
  Expected: {what should happen}

What is the actual behaviour?
  Actual: {what actually happens — exact error message, wrong value, etc.}

Is it deterministic or intermittent?
  Deterministic: always happens with the same input
  Intermittent: happens sometimes — need to identify the trigger

Reproduction steps:
  1. {exact step}
  2. {exact step}
  3. {exact step}
  → Bug occurs
```

### Minimal Reproduction

Reduce the reproduction to the smallest possible case. Remove everything that is not necessary to trigger the bug.

```python
# Write a failing test that reproduces the bug
# This serves two purposes:
# 1. Confirms you can reproduce it reliably
# 2. Becomes the verification test when you fix it

# Example: failing test for a search bug
@pytest.mark.unit
async def test_search_returns_no_results_for_valid_query():
    """Reproduces: search returns empty results for query 'AI chatbot'."""
    service = SearchService()
    results = await service.search("AI chatbot")
    # This should NOT be empty — but it is
    assert len(results) > 0, f"Expected results, got empty list for 'AI chatbot'"
```

If you cannot write a failing test, you do not have a reliable reproduction. Keep investigating until you can.

## Step 2: Gather Evidence

Collect data before forming hypotheses. Evidence first, theory second.

### 2a. Read the Error Message Completely

Never skip or paraphrase the error message. Read every word.

```python
# Get the full error with stack trace
Bash(
    command="docker compose logs backend --tail=200 2>&1"
)

# Get recent errors from the application logs
Bash(
    command="docker compose logs backend --since=1h 2>&1 | grep -i 'error\\|exception\\|traceback' | head -50"
)
```

What to look for in the error message:
- The exception type (e.g., `SynchronousOnlyOperation`, `IntegrityError`, `KeyError`)
- The file and line number where it occurred
- The full stack trace — the root cause is often several frames up from the surface error
- Any contextual values in the error (user ID, query string, model name)

### 2b. Check the Logs

```python
# Backend logs
Bash(
    command="docker compose logs backend --tail=100 2>&1"
)

# Frontend logs (browser console errors)
# These require manual inspection in browser DevTools

# Database logs (for query issues)
Bash(
    command="docker compose logs db --tail=50 2>&1"
)

# Check for recent structlog entries with context
Bash(
    command="docker compose logs backend --tail=200 2>&1 | python3 -c \"import sys,json; [print(json.dumps(json.loads(l), indent=2)) for l in sys.stdin if l.strip().startswith('{')]\" 2>/dev/null | head -100"
)
```

### 2c. Check Recent Changes

The bug probably started when something changed. Find what changed.

```python
# What changed in the last 5 commits?
Bash (git diff)(base="HEAD~5", stat_only=True)

# What changed in the specific file where the bug occurs?
Bash(
    command="git log --oneline -10 -- backend/src/cv_builder/{app}/{file}.py"
)

# What did the last commit change?
Bash (git diff)(base="HEAD~1")
```

### 2d. Read the Relevant Code

Read the code that is failing. Do not rely on memory.

```python
# Read the failing function
Read(
    path="backend/src/cv_builder/{app}/{file}.py",
    symbol="{function_name}"
)

# Find all callers of the failing function
Bash (grep for callers)(
    symbol="{function_name}",
    path="backend/src/cv_builder/"
)

# Read the test for the failing function
Bash (grep/rg)(
    pattern="def test.*{function_name}|{function_name}.*test",
    path="backend/tests/"
)
```

### 2e. Check the Configuration

Many bugs are configuration bugs, not code bugs.

```python
# Check settings classes use BaseSettings (not BaseModel — silently ignores env vars)
Bash (grep/rg)(
    pattern="class.*Settings.*BaseModel",
    path="backend/src/cv_builder/"
)
# Any match is a potential config bug — should be BaseSettings

# Check for lru_cache on config functions (stale config in tests)
Bash (grep/rg)(
    pattern="@lru_cache",
    path="backend/src/cv_builder/"
)

# Check environment variables are set
Bash(
    command="docker compose exec backend env | grep -i '{relevant_var}'"
)
```

### Evidence Log Template

Document what you found before forming a hypothesis:

```
Evidence gathered:

1. Error message: {exact error text}
   File: {file:line}
   Stack trace: {key frames}

2. Recent changes: {what changed in the last N commits}
   Most suspicious: {which change is most likely related}

3. Code reading: {what the code actually does}
   Discrepancy: {how it differs from what you expected}

4. Configuration: {relevant config values}
   Issue: {any misconfiguration found}

5. Logs: {relevant log entries}
   Pattern: {what the logs reveal}
```

## Step 3: Form ONE Hypothesis

Based on the evidence, form a single hypothesis. Not two. Not "it could be A or B". One.

### Hypothesis Template

```
Hypothesis: I believe the bug is caused by {specific cause} because {evidence that supports this}.

What would prove this hypothesis:
  - {observable outcome if hypothesis is correct}

What would disprove this hypothesis:
  - {observable outcome if hypothesis is wrong}

Confidence: {LOW / MEDIUM / HIGH}
  LOW: I'm guessing based on limited evidence
  MEDIUM: Evidence points here but I haven't confirmed it
  HIGH: Multiple pieces of evidence converge on this cause
```

### Why One Hypothesis?

Testing multiple hypotheses simultaneously means you cannot isolate the cause. If you change two things and the bug goes away, you don't know which change fixed it — or if both were needed. Change one variable at a time.

### Common Hypothesis Patterns for cv-builder

| Symptom | Common Root Cause | Hypothesis to Test |
|---------|------------------|-------------------|
| `SynchronousOnlyOperation` | Blocking ORM call in async view | ORM call not wrapped in `sync_to_async` |
| Config value ignored | `BaseModel` instead of `BaseSettings` | Settings class extends wrong base |
| Duplicate results | Missing `.distinct()` on M2M query | M2M filter without `.distinct()` |
| Hydration mismatch | `window`/`document` access outside `onMounted` | SSR renders different HTML than client |
| Rate limit not working | `LocMemCache` instead of Redis | Cache backend is in-memory, not shared |
| Stale config in tests | `@lru_cache` not cleared | `get_config.cache_clear()` not called |
| Search returns no results | `vec_sim_floor` too high | Similarity threshold filtering all results |
| Token not refreshing | Cookie not sent cross-origin | `credentials: 'include'` missing in fetch |

## Step 4: Test the Hypothesis

Change ONE variable to test the hypothesis. Observe the result.

### Testing Approach

```python
# Option A: Write a targeted test
@pytest.mark.unit
async def test_hypothesis_{n}():
    """Tests hypothesis: {hypothesis statement}."""
    # Set up the specific condition the hypothesis predicts
    # ...
    # Observe the outcome
    result = await {function}({inputs})
    # Assert what the hypothesis predicts
    assert {expected_outcome}, f"Hypothesis failed: {result}"
```

```python
# Option B: Add a debug assertion to the code
# (temporary — remove after investigation)
async def {function}({params}):
    # DEBUG: testing hypothesis that {X} is None here
    assert {X} is not None, f"Hypothesis confirmed: {X} is None at this point"
    # ... rest of function
```

```python
# Option C: Add targeted logging
import structlog
logger = structlog.get_logger()

async def {function}({params}):
    logger.debug("investigating_{function}", value={X}, type=type({X}).__name__)
    # ... rest of function
```

### If the Hypothesis is Wrong

Return to Step 2 with new evidence. The failed test IS evidence — it tells you what the bug is NOT.

```
Hypothesis {n} disproved.
New evidence: {what the failed test revealed}
Revised understanding: {how your mental model changed}
Next hypothesis: {new hypothesis based on updated evidence}
```

### If the Hypothesis is Correct

The failing test now passes when you make the minimal change. Proceed to Step 5.

## Step 5: Fix and Verify

Once the root cause is confirmed, implement the fix.

### Fix Principles

- Fix the root cause, not the symptom
- Make the minimal change that fixes the root cause
- Do not refactor while fixing — that's a separate commit
- Do not add defensive code that hides the bug — fix it properly

### Verification Steps

```python
# 1. The failing test from Step 1 now passes
Bash (pytest)(
    path="backend/tests/unit/{app}/test_{file}.py",
    flags=["-x", "-v", "-k", "test_{bug_reproduction}"]
)

# 2. The full test suite still passes (no regressions)
Bash (pytest)(
    path="backend/tests/unit/{app}/",
    flags=["-x", "-q"]
)

# 3. No type errors introduced
Bash(command="uv run ruff check backend/src/cv_builder/{app}/{file}.py && uv run basedpyright backend/src/cv_builder/{app}/{file}.py")

# 4. No lint violations
Bash(command="uv run ruff check backend/src/cv_builder/{app}/")
```

### Document the Root Cause

Write a comment in the code explaining WHY the fix is correct, not just WHAT it does:

```python
# ✅ Good comment — explains the root cause
# M2M queries produce duplicate rows when a vendor matches multiple taxonomy nodes.
# .distinct() is required to deduplicate. See ADR-0022.
vendors = Vendor.objects.filter(
    taxonomy_nodes__slug__in=slugs
).distinct()

# ❌ Bad comment — describes what the code does, not why
# Add distinct to remove duplicates
vendors = Vendor.objects.filter(
    taxonomy_nodes__slug__in=slugs
).distinct()
```

Store the investigation findings in basic-memory for future reference:

```python
mcp_basic_memory_write_note(
    title="{bug-description}-root-cause-{date}",
    directory="findings",
    content="""
## Root Cause: {bug description}

**Symptom**: {what was observed}
**Root cause**: {what actually caused it}
**Fix**: {what was changed}
**Why it works**: {explanation}
**Related**: ADR-{N}, {file:line}
**Pattern**: {generalised pattern for future reference}
"""
)
```

## The 3-Fix Escalation Rule

If 3 fix attempts fail, STOP. Do not attempt fix #4.

Three failed fixes means the root cause analysis is wrong. More attempts will waste time and potentially introduce new bugs. At this point:

1. **Document what you know**: what you've tried, what evidence you have, what hypotheses were disproved
2. **Escalate to the user**: present the evidence and ask for a different perspective
3. **Consider a different approach**: maybe the bug is in a different layer than you think

```
## Escalation Report: {bug description}

**Attempts made**: 3
**Hypotheses tested**:
  1. {hypothesis 1} — DISPROVED because {evidence}
  2. {hypothesis 2} — DISPROVED because {evidence}
  3. {hypothesis 3} — DISPROVED because {evidence}

**Current evidence**:
  - {evidence 1}
  - {evidence 2}

**What I don't understand**:
  - {specific gap in understanding}

**Possible root causes I haven't been able to test**:
  - {untested hypothesis 1}
  - {untested hypothesis 2}

**Request**: {specific help needed — e.g., "access to production logs", "pair debugging session", "architectural review"}
```

## cv-builder-Specific Investigation Patterns

Six recurring root-cause patterns live in `references/failure-patterns-verifai.md`. Load that file when the bug's symptom matches one of these — it contains the detection grep + fix pattern for each:

| Symptom | Likely pattern |
|---|---|
| `SynchronousOnlyOperation`, hanging ORM | Blocking ORM in async view (ADR-0006) |
| Env var has no effect on config | `BaseModel` instead of `BaseSettings` |
| Duplicate vendors in search results | M2M query without `.distinct()` |
| Rate limit allows too many requests | `LocMemCache` in production |
| Monkeypatched env var ignored in tests | `@lru_cache` not cleared |

Read `references/failure-patterns-verifai.md` with the Read tool when you need the full detection grep + fix pattern for one of these symptoms. The file is loaded on-demand; it does not consume context until the symptom matches.

If none of the six patterns match, return to the main flow — form a fresh hypothesis from scratch using the Iron Law protocol above.
