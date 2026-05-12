---
name: qa-methodology
description: "Structured QA methodology with per-page checklists and health scoring. Use when performing a quality review of a feature, page, or component before release. Produces a health score (0-100) across functionality, error handling, accessibility, tests, and security dimensions with weighted scoring. Covers cv-builder-specific checks: async safety (ADR-0006), JWT cookie storage (ADR-0013), M2M distinct queries, organisation scoping, and three-valued compliance display. Ideal before demo deployments or PR merges to catch regressions before clients see them. Activates on: QA checklist, quality methodology, page-by-page review, health score, quality review, feature QA, pre-release check, quality audit, test coverage review, QA pass, demo readiness check, release gate."
metadata:
  category: quality
  complexity: 3
  activation_examples:
    - "QA checklist for the vendor comparison feature before demo"
    - "quality review of the search page — health score"
    - "pre-release QA pass on the shortlist management UI"
    - "page-by-page quality audit of the authentication flow"
    - "health score for the vendor enrichment pipeline"
  related_steering:
    - testing-standards
    - review-protocol
---

# QA Methodology Skill

Structured quality assurance with per-page checklists and weighted health scoring. Adapted from garrytan/gstack (MIT). Use before any demo, release, or PR merge to get an objective health score and a prioritised fix list.

## When to Activate

- Before a demo or client presentation (hard deadlines: 8 May and 14 May 2026)
- Before marking a spec phase complete
- When a feature has been implemented but not formally reviewed
- When a bug report suggests systemic quality issues
- After a significant refactor to verify nothing regressed

## Step 1: Define Scope

Identify exactly what is being reviewed. Be specific — vague scope produces vague results.

```
Pages / components to review:
  - [ ] {page or component name} — {route or file path}
  - [ ] {page or component name} — {route or file path}

Backend features to review:
  - [ ] {endpoint or service} — {file path}

Out of scope (document explicitly):
  - {anything deliberately excluded and why}
```

For cv-builder, typical scope for a feature QA pass:
- Frontend: the page(s) in `frontend/pages/` and key components in `frontend/components/`
- Pipeline: the PydanticAI agent, output_validator, scoring/rendering stages
- Tests: unit tests in `backend/tests/unit/` and `frontend/**/*.test.ts`

## Step 2: Per-Page / Per-Component Checklist

Run this checklist for each item in scope. Use tool calls to verify where possible.

### 2a. Functionality

Does it do what the spec says?

```python
# Read the spec requirements
Read(path=".claude/specs/{spec-name}/requirements.md")

# Verify the implementation matches
Read(path="backend/src/cv_builder/{app}/services.py")
Read(path="frontend/pages/{page}.vue")
```

Checklist:
- [ ] All acceptance criteria from the spec are implemented
- [ ] Happy path works end-to-end
- [ ] Edge cases handled (empty state, single item, maximum items)
- [ ] Loading states are shown during async operations
- [ ] Error states are shown when operations fail

### 2b. Error States

Are all three states handled?

```python
# Check for empty state handling
Bash (grep/rg)(
    pattern="v-if.*\\.length === 0|empty|no.results|no.vendors",
    path="frontend/pages/{page}.vue"
)

# Check for loading state
Bash (grep/rg)(
    pattern="loading|isLoading|status.*pending",
    path="frontend/pages/{page}.vue"
)

# Check for error state
Bash (grep/rg)(
    pattern="error|isError|status.*error",
    path="frontend/pages/{page}.vue"
)
```

Checklist:
- [ ] Empty state: shown when there is no data (not a blank page)
- [ ] Loading state: shown while data is fetching (spinner, skeleton, or placeholder)
- [ ] Error state: shown when the API call fails (not a silent failure)
- [ ] Error messages are user-friendly (not raw stack traces or HTTP status codes)

### 2c. Accessibility (WCAG 2.1 AA)

```python
# Check for ARIA labels on interactive elements
Bash (grep/rg)(
    pattern="aria-label|aria-describedby|aria-invalid|role=",
    path="frontend/pages/{page}.vue"
)

# Check for form labels
Bash (grep/rg)(
    pattern="<label|for=|htmlFor=",
    path="frontend/pages/{page}.vue"
)

# Check for alt text on images
Bash (grep/rg)(
    pattern="<img(?!.*alt=)|alt=\"\"",
    path="frontend/pages/{page}.vue"
)
```

Checklist:
- [ ] All form inputs have associated `<label>` elements
- [ ] Interactive elements have `aria-label` or visible text
- [ ] Error messages use `role="alert"` for screen reader announcement
- [ ] Images have meaningful `alt` text (or `alt=""` for decorative images)
- [ ] Keyboard navigation works: Tab, Enter, Escape, arrow keys where applicable
- [ ] Focus is visible (not hidden by `outline: none` without replacement)
- [ ] Colour contrast meets AA (4.5:1 for normal text, 3:1 for large text)

Note: Full WCAG validation requires manual testing with assistive technologies. Tool checks above catch common structural issues only.

### 2d. Responsive Design

Checklist (manual verification required):
- [ ] Desktop (1280px): layout is correct, no overflow, no truncated text
- [ ] Tablet (1024px): layout adapts, no horizontal scroll
- [ ] Mobile (390px): layout stacks correctly, touch targets ≥44px

```python
# Check for responsive Tailwind classes
Bash (grep/rg)(
    pattern="sm:|md:|lg:|xl:",
    path="frontend/pages/{page}.vue"
)
```

### 2e. Performance

```python
# Check for N+1 query patterns — ORM calls inside loops
Bash (grep/rg)(
    pattern="for.*in.*:\n.*\.objects\.|for.*in.*:\n.*await.*sync_to_async",
    path="backend/src/cv_builder/{app}/services.py",
    multiline=True
)

# Check for select_related / prefetch_related on M2M queries
Bash (grep/rg)(
    pattern="select_related|prefetch_related",
    path="backend/src/cv_builder/{app}/"
)

# Check for blocking ORM calls in async views (ADR-0006)
Bash (grep/rg)(
    pattern="^(?!.*sync_to_async).*\.objects\.",
    path="backend/src/cv_builder/{app}/routers.py"
)
```

Checklist:
- [ ] No N+1 queries — related objects loaded with `select_related`/`prefetch_related`
- [ ] No blocking ORM calls in async views (ADR-0006) — all ORM inside `sync_to_async`
- [ ] M2M queries use `.distinct()` to avoid duplicate results
- [ ] Pagination applied to list endpoints (no unbounded queries)
- [ ] Frontend: no unnecessary re-renders (computed properties used correctly)

### 2f. Security

```python
# Check auth is applied to protected endpoints
Bash (grep/rg)(
    pattern="auth=JWTAuth()",
    path="backend/src/cv_builder/{app}/routers.py"
)

# Check organisation scoping (no cross-tenant leakage)
Bash (grep/rg)(
    pattern="request\.auth\.organization|filter.*organization",
    path="backend/src/cv_builder/{app}/"
)

# Check CSRF protection on mutations
Bash (grep/rg)(
    pattern="useApi\(\)",
    path="frontend/pages/{page}.vue"
)

# Check for v-html without DOMPurify
Bash (grep/rg)(
    pattern="v-html(?!.*DOMPurify|.*sanitise)",
    path="frontend/pages/{page}.vue"
)
```

Checklist:
- [ ] Auth required on all protected endpoints (`auth=JWTAuth()`)
- [ ] CSRF protected: mutations use `useApi()` composable, not raw `$fetch`
- [ ] Input validated via Pydantic v2 schemas (not raw `request.body`)
- [ ] Organisation scoping on all queries (no cross-tenant data leakage)
- [ ] No `v-html` without DOMPurify sanitisation
- [ ] No secrets or tokens in frontend code or localStorage

### 2g. Tests

```python
# Check unit tests exist
Bash (grep/rg)(
    pattern="def test_",
    path="backend/tests/unit/{app}/"
)

# Check frontend tests exist
Bash (grep/rg)(
    pattern="it\(|test\(",
    path="frontend/tests"
)

# Run the tests
Bash (pytest)(
    path="backend/tests/unit/{app}/",
    flags=["-x", "-q"]
)
Bash (pnpm exec vitest run)(path="frontend")
```

Checklist:
- [ ] Unit tests exist for the service layer
- [ ] Unit tests cover the happy path
- [ ] Unit tests cover at least one error path
- [ ] Frontend component tests exist (if component has logic)
- [ ] All tests pass

## Step 3: Health Scoring

Score each dimension 0–10 for each page/component reviewed. Then compute the weighted overall score.

### Scoring Rubric

| Score | Meaning |
|-------|---------|
| 10 | Fully implemented, no issues found |
| 8–9 | Minor issues (cosmetic, low-risk) |
| 6–7 | Moderate issues (some edge cases missing) |
| 4–5 | Significant issues (key paths broken or missing) |
| 2–3 | Major issues (feature partially implemented) |
| 0–1 | Critical issues (feature non-functional or security risk) |

### Dimension Weights

| Dimension | Weight | Score (0–10) | Weighted Score |
|-----------|--------|-------------|----------------|
| Functionality | 30% | {score} | {score × 0.30} |
| Error handling | 20% | {score} | {score × 0.20} |
| Accessibility | 20% | {score} | {score × 0.20} |
| Tests | 20% | {score} | {score × 0.20} |
| Security | 10% | {score} | {score × 0.10} |
| **Overall** | 100% | — | **{sum × 10}** |

**Overall health score = sum of weighted scores × 10** (result is 0–100)

### Health Score Interpretation

| Score | Status | Action |
|-------|--------|--------|
| 90–100 | ✅ Excellent | Ready for release |
| 75–89 | ✅ Good | Minor fixes before release |
| 60–74 | ⚠️ Acceptable | Address medium issues before release |
| 40–59 | ⚠️ Poor | Address high issues before release |
| 0–39 | ❌ Critical | Do not release — critical issues must be fixed |

## Step 4: Prioritised Fix List

Categorise every issue found into one of four priorities.

### Priority Definitions

| Priority | Definition | Examples |
|----------|-----------|---------|
| **Critical** | Blocks release — security vulnerability, data loss, auth bypass, broken core flow | Cross-tenant data leak, JWT in localStorage, broken login |
| **High** | Should fix before release — broken edge case, missing error state, accessibility blocker | Empty state shows blank page, form submits without validation |
| **Medium** | Fix in next sprint — cosmetic issue, minor UX problem, missing test | Button misaligned on mobile, missing unit test for error path |
| **Low** | Nice to have — minor improvement, refactor opportunity | Inconsistent spacing, could use a composable |

### Fix List Template

```
## Critical (blocks release)
- [ ] {issue description} — {file:line} — {fix required}

## High (fix before release)
- [ ] {issue description} — {file:line} — {fix required}

## Medium (fix in next sprint)
- [ ] {issue description} — {file:line} — {fix required}

## Low (nice to have)
- [ ] {issue description} — {file:line} — {fix required}
```

## Step 5: QA Report

Produce a structured QA report. This is the deliverable.

```
## QA Report: {Feature / Page Name}

**Spec**: {spec-name}
**Reviewed by**: {agent or person}
**Date**: {date from Bash (date)()}
**Scope**: {list of pages/components reviewed}

---

### Health Score Summary

| Page / Component | Func | Errors | A11y | Tests | Security | Score |
|-----------------|------|--------|------|-------|----------|-------|
| {page 1} | {n}/10 | {n}/10 | {n}/10 | {n}/10 | {n}/10 | **{score}/100** |
| {page 2} | {n}/10 | {n}/10 | {n}/10 | {n}/10 | {n}/10 | **{score}/100** |
| **Overall** | — | — | — | — | — | **{avg}/100** |

---

### Prioritised Fix List

#### Critical (blocks release)
{list or "None"}

#### High (fix before release)
{list or "None"}

#### Medium (fix in next sprint)
{list or "None"}

#### Low (nice to have)
{list or "None"}

---

### ADR Compliance

| ADR | Check | Result |
|-----|-------|--------|
| ADR-0006 | All views async | ✅ / ❌ |
| ADR-0013 | JWT in httpOnly cookies | ✅ / ❌ |
| ADR-0025 | Schemas use CamelSchema | ✅ / ❌ |

---

### Recommendation

**Status**: PASS / CONDITIONAL PASS / FAIL
**Release decision**: {ready / fix critical issues first / do not release}
**Estimated fix time**: {hours}
```

## cv-builder-Specific QA Patterns

### Vendor Search Page QA

Key checks specific to the search feature:
- Search returns results within 500ms P95 (check `docs/SEARCH.md` for targets)
- RRF scores are in [0, 1] range
- Empty query shows helpful prompt, not an error
- Taxonomy filter chips update results correctly
- Pagination works at boundaries (first page, last page, single page)

### Authentication Flow QA

Key checks specific to auth (ADR-0013):
- Login sets httpOnly cookies (verify in browser DevTools → Application → Cookies)
- Logout clears both access and refresh tokens
- Expired access token triggers silent refresh (not a logout)
- Rate limiting fires after 5 failed login attempts (ADR-0021)
- Invitation flow: invited user can register, uninvited cannot

### Vendor Comparison QA

Key checks specific to the comparison feature:
- Comparison table renders correctly with 2, 3, and 4 vendors
- Compliance fields show ternary state: ✓ (true), ✗ (false), ? (null)
- Export/share works correctly
- Organisation scoping: users cannot see other orgs' shortlists

### Referencing Steering Files

For deeper guidance on specific areas:
- Testing patterns → `testing-standards.md`
- Security checks → `security-standards.md`
- Async safety → `django-patterns.md` (ADR-0006 section)
- Accessibility → WCAG 2.1 AA (manual testing required beyond tool checks)
