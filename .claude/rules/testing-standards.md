# Testing Standards

Reference: `tests/` directory. Framework: pytest + Hypothesis + testmon + pytest-benchmark.

## Test pyramid

| Level | % | Tools | Speed | Location |
|-------|---|-------|-------|----------|
| Unit | 70% | pytest | <1s | `tests/unit/` |
| Integration | 15% | pytest, real LanceDB | 1-10s | `tests/integration/` |
| Property | 10% | Hypothesis | <1s | alongside unit tests |
| E2E / scraper | 5% | Nova Act recorded fixtures | >10s | `tests/e2e/` |

## Running tests

```bash
uv run pytest -q --no-header                          # testmon cached (affected only)
uv run pytest -q --no-header -m "not integration and not slow"  # fast subset
uv run pytest --testmon-noselect                      # ignore testmon cache
uv run pytest tests/unit/ -x -q                       # specific dir
uv run pytest tests/ -k "test_slop" -v                # by name pattern
```

## Pytest markers

```python
@pytest.mark.unit           # fast, no external deps
@pytest.mark.integration    # touches LanceDB / files
@pytest.mark.slow           # >10 seconds
@pytest.mark.scraper        # Nova Act / CDP — requires NOVA_ACT_API_KEY
@pytest.mark.benchmark      # pytest-benchmark timing
```

## PydanticAI test pattern

```python
# conftest.py
import pydantic_ai.models
pydantic_ai.models.ALLOW_MODEL_REQUESTS = False  # fail if any test hits real Bedrock

# test file
from pydantic_ai.models.test import TestModel

async def test_jd_analyzer_extracts_keywords():
    with jd_analyzer.override(model=TestModel()):
        result = await jd_analyzer.run("Python backend engineer with AWS experience")
        assert result.output.keywords is not None
```

## Hypothesis — property testing

Always use `@settings(deadline=None)` to avoid CI flakiness.

```python
from hypothesis import given, settings, strategies as st

@given(text=st.text(min_size=1, max_size=500))
@settings(max_examples=100, deadline=None)
def test_slop_detection_never_crashes(text: str):
    """Property: slop detector handles any string input without exception."""
    result = detect_slop(text)
    assert isinstance(result, SlopResult)
    assert 0.0 <= result.score <= 1.0
```

Property-test triggers:
1. Writing a new pure function
2. Fixing a bug (regression property)
3. Modifying a function that affects ordering/bounds

Naming: `test_p_<type>_<description>` — e.g. `test_p_monotonicity_ats_score`.

## Floating-point assertions

```python
assert total_score == pytest.approx(1.0, abs=1e-3)  # ✅ tolerant
assert total_score == 1.0                            # ❌ fails on drift
```

## Nova Act test recordings

Nova Act provides recording/replay for scraper tests. Record fixtures, commit to `tests/e2e/fixtures/`, replay in CI. Never hit real LinkedIn in CI.

## Coverage targets

| Scope | Minimum | Target |
|-------|---------|--------|
| Overall | 70% | 80% |
| New modules | — | 80%+ |
| Scoring (ATS critical path) | 90% | 95% |

## Rules summary

1. Every write path needs a read path — test creating AND reading back.
2. No assertion-free tests — every test asserts something meaningful.
3. `@pytest.mark.asyncio` where needed (pyproject.toml may set `asyncio_mode=auto`).
4. Skip with documented reason: `@pytest.mark.skip(reason="tracks issue #N: ...")`.
5. No real Bedrock calls — `ALLOW_MODEL_REQUESTS=False` enforced.
6. No real LinkedIn scrapes in CI — use recorded fixtures.
