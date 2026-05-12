---
name: validate-delivery
description: "Validates that delivered code meets all acceptance criteria from the spec. Use after completing a task or phase, before marking work as done, or when reviewing a PR. Runs through each acceptance criterion systematically and verifies it with tool calls — never from memory. Runs five mandatory quality gates: ruff+basedpyright, pytest, ruff, agentsys-style config lint (for .claude/ changes), and vitest (for frontend). Produces a structured delivery report with grounded evidence for every claim. Activates on: validate delivery, check acceptance criteria, verify implementation, is this done, validate the work, acceptance criteria check, delivery validation, does this meet the requirements, quality gate, preflight check, task completion verification, ready to merge, mark complete."
metadata:
  category: quality
  complexity: 2
  activation_examples:
    - "validate delivery of the vendor search endpoint"
    - "is this done? check acceptance criteria for task 2.3"
    - "quality gate before I mark phase 1 complete"
    - "does this meet the requirements for the authentication module?"
    - "preflight check before raising the PR"
  related_steering:
    - testing-standards
    - preflight-quality
---

# Validate Delivery Skill

Validates that delivered code meets all acceptance criteria from the spec. Adapted from agent-sh/agentsys v5.8.3 (MIT). This skill is the final gate before marking any task `[x]` or raising a PR.

## When to Activate

- After completing a task or phase — before marking `[x]` in `tasks.md`
- Before raising a PR — ensures the PR description can cite verified evidence
- When a sub-agent reports DONE — verify the claims before accepting
- When reviewing a PR from another developer
- After a bug fix — verify the fix doesn't break acceptance criteria

## Step 1: Load Acceptance Criteria

Read the relevant spec task and extract its acceptance criteria:

```python
Read(path=".claude/specs/{spec-name}/tasks.md")
```

For the task being validated, extract:
- The task description
- Each acceptance criterion (AC lines)
- Any requirement references (`_Requirements: AC-X.Y_`)
- The agent assigned (`_Agent: ...`)

If the task has no acceptance criteria, that's a spec quality issue — flag it and use the task description as the implicit criterion.

## Step 2: Classify Each Criterion

For each acceptance criterion, classify it before attempting verification:

| Type | Description | Verification Method |
|---|---|---|
| **Tool-verifiable** | File exists, pattern present, test passes | `grep_search`, `get_file_info`, `run_pytest` |
| **App-verifiable** | Endpoint returns correct response, UI renders | `run_pytest` with integration test, or manual |
| **Human-judgment** | UX quality, code readability, architectural fit | Flag for human review |

Most acceptance criteria in cv-builder specs are tool-verifiable. If a criterion can't be verified by a tool call, flag it explicitly in the delivery report.

## Step 3: Verify Tool-Verifiable Criteria

Run the appropriate tool for each criterion. Use parallel tool calls where possible.

**File existence** — "The file `{path}` exists":
```python
Bash (stat)(path="backend/src/cv_builder/{app}/{file}.py")
```

**Function/class exists** — "The service method `{name}` is implemented":
```python
Bash (grep for symbol)(name="{function_name}", path="backend/src/cv_builder/")
# or
Bash (grep/rg)(
    pattern="async def {function_name}",
    path="backend/src/cv_builder/{app}/services.py"
)
```

**Endpoint registered** — "The API endpoint `GET /api/{path}/` is available":
```python
Bash (grep/rg)(
    pattern='@router\.(get|post|put|delete)\("/{path}',
    path="backend/src/cv_builder/{app}/routers.py"
)
```

**Schema compliance** — "Response schema uses camelCase (ADR-0025)":
```python
Bash (grep/rg)(
    pattern="class {SchemaName}.*CamelSchema",
    path="backend/src/cv_builder/{app}/schemas.py"
)
```

**Async compliance** — "View is async (ADR-0006)":
```python
Bash (grep/rg)(
    pattern="async def {function_name}",
    path="backend/src/cv_builder/{app}/routers.py"
)
```

**Test exists** — "Unit tests cover the happy path and error paths":
```python
Bash (grep/rg)(
    pattern="def test_{feature}",
    path="backend/tests/unit/{app}/"
)
```

**Type safety** — "No type errors in modified files":
```python
Bash(command="uv run ruff check backend/src/cv_builder/{app}/services.py backend/src/cv_builder/{app}/schemas.py && uv run basedpyright backend/src/cv_builder/{app}/")
])
```

## Step 4: Run Quality Gates

Always run these quality gates regardless of what the acceptance criteria say. These are non-negotiable for any delivery.

### Gate 1: ruff + basedpyright (mandatory)

```python
Bash(command="uv run ruff check backend/src/cv_builder/{app}/routers.py backend/src/cv_builder/{app}/services.py backend/src/cv_builder/{app}/schemas.py && uv run basedpyright backend/src/cv_builder/{app}/")
# Expected: 0 errors, 0 warnings
# If errors found: fix before reporting DONE
```

### Gate 2: pytest on relevant test directory (mandatory for backend changes)

```python
Bash (pytest)(
    path="backend/tests/unit/{app}/",
    flags=["-x", "-q"]
)
# Expected: all tests pass
# If failures: fix before reporting DONE
```

### Gate 3: ruff on modified Python files (mandatory for backend changes)

```python
Bash (ruff)(
    path="backend/src/cv_builder/{app}/",
)
# Expected: 0 violations
# If violations: run with fix=True for auto-fixable, manually fix the rest
```

### Gate 4: .claude/ config lint (mandatory if .claude/ files changed)

Post-Kiro replacement for the old `validate_config.py`: run ruff + basedpyright against agent / skill / rule frontmatter and Python in `.claude/skills/**/scripts/`.

```python
Bash(
    command="uv run ruff check .claude/ && uv run basedpyright .claude/"
)
# Expected: exit 0, no errors
# Also: every .claude/agents/*.md and .claude/skills/*/SKILL.md has valid YAML frontmatter
#       (name, description; model+effort on agents). No Kiro-legacy constructs.
```

### Gate 5: Frontend vitest (mandatory for frontend changes)

```python
Bash (pnpm exec vitest run)(path="frontend")
# Expected: all tests pass
# If failures: fix before reporting DONE
```

## Step 5: Delivery Report

Produce a structured delivery report. This is the evidence that the task is genuinely complete.

```
## Delivery Validation Report

**Task**: {task number and description}
**Spec**: {spec-name}
**Validated by**: {agent name}
**Date**: {date from Bash (date)()}

### Acceptance Criteria

✅ **AC-N.N.1**: {criterion text}
   Evidence: grep_search on {file} found `{pattern}` at line {N}

✅ **AC-N.N.2**: {criterion text}
   Evidence: `Bash(ruff check {file} && basedpyright {file})` → 0 errors

❌ **AC-N.N.3**: {criterion text}
   Missing: {what's not implemented}
   Action required: {specific fix needed}

⚠️ **AC-N.N.4**: {criterion text}
   Requires human judgment: {what needs manual verification}

### Quality Gates

| Gate | Result | Details |
|---|---|---|
| ruff + basedpyright | ✅ PASS | 0 errors, 0 warnings on 3 files |
| pytest | ✅ PASS | 12 passed, 0 failed in 2.3s |
| ruff | ✅ PASS | 0 violations |
| .claude/ config lint | N/A | No .claude/ files modified |
| vitest | N/A | No frontend files modified |

### ADR Compliance

| ADR | Check | Result |
|---|---|---|
| ADR-0006 | All views are async | ✅ PASS |
| ADR-0023 | Tests use real PostgreSQL | ✅ PASS |
| ADR-0025 | Schemas use CamelSchema | ✅ PASS |

### Overall

**Status**: PASS / FAIL / PARTIAL
**Blocking issues**: {count}
**Criteria met**: {N}/{total}
**Recommendation**: {mark [x] and proceed / fix issues before marking complete}
```

## cv-builder-Specific Validation Patterns

### Validating a new PydanticAI agent

```python
# 1. Endpoint is registered
Bash (grep/rg)(pattern='@router\.(get|post)', path="backend/src/cv_builder/{app}/routers.py")

# 2. View is async
Bash (grep/rg)(pattern="async def {endpoint_name}", path="backend/src/cv_builder/{app}/routers.py")

# 3. Auth is applied (JWTAuth)
Bash (grep/rg)(pattern="auth=JWTAuth()", path="backend/src/cv_builder/{app}/routers.py")

# 4. Response schema uses CamelSchema
Bash (grep/rg)(pattern="class.*Out.*CamelSchema", path="backend/src/cv_builder/{app}/schemas.py")

# 5. Organisation scoping (no cross-tenant leakage)
Bash (grep/rg)(pattern="request\.auth\.organization", path="backend/src/cv_builder/{app}/")

# 6. Tests exist
Bash (grep/rg)(pattern="def test_{endpoint_name}", path="backend/tests/unit/{app}/")
```

### Validating a new Pydantic schema

```python
# 1. Inherits from CamelSchema (ADR-0025)
Bash (grep/rg)(pattern="class {SchemaName}.*CamelSchema", path="backend/src/")

# 2. No BaseModel without alias_generator
Bash (grep/rg)(pattern="class {SchemaName}.*BaseModel", path="backend/src/")
# This should return NO results for API response schemas

# 3. Settings classes use BaseSettings
Bash (grep/rg)(pattern="class.*Settings.*BaseSettings", path="backend/src/")
```

### Validating a new rendercv template

```python
# 1. Uses script setup with TypeScript
Bash (grep/rg)(pattern="<script setup lang=\"ts\">", path="frontend/components/{ComponentName}.vue")

# 2. No window/document outside onMounted
Bash (grep/rg)(pattern="window\.|document\.", path="frontend/components/{ComponentName}.vue")
# Any match outside onMounted is an SSR safety violation

# 3. Uses useApi() for mutations (not raw $fetch)
Bash (grep/rg)(pattern="\$fetch.*method.*POST|PUT|DELETE", path="frontend/components/{ComponentName}.vue")
# Should return NO results — mutations must use useApi()
```

### Validating .claude/ configuration changes

```python
# Run the full validation suite
Bash(
    command="uv run --directory .claude/mcp --package verifai-kiro-checks validate-config"
)
# Check for: PASS (green), WARN (yellow — investigate), FAIL (red — must fix)
```
