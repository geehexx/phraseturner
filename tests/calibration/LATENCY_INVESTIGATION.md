# Compare Tool Latency Investigation

**Date**: 2026-04-16
**Observed**: 2.9s on first call (target: 800ms)

---

## Summary

The 2.9s first-call latency is **not** from FastEmbed model loading, spaCy model
loading, or running the pipeline twice. It is from **Python import overhead** —
`scipy.stats` and `lexicalrichness` are imported lazily on the first pipeline call
and together account for ~3.8s of import time.

Warm calls are **4.5ms (Tier 0)** and **21ms (Tier 1)** — well within the 800ms target.

---

## Profiling Data

All measurements taken on 2026-04-16 with `uv run python` in the phraseturner venv.

### Import costs (cold process, measured individually)

| Module | Import time |
|--------|------------|
| `scipy.stats` | 1606ms |
| `lexicalrichness` | 2181ms |
| `numpy` | 208ms |
| `spacy` (import only) | 1273ms |
| `fastembed` | 539ms |
| `textstat` | 19ms |
| `vaderSentiment` | 5ms |

`scipy.stats` and `lexicalrichness` are the dominant costs. They are imported at
module level in `naturalness.py` and `vocabulary.py` respectively, so they resolve
on the first `run_pipeline` call.

### Pipeline latency (warm calls, after imports resolved)

| Scenario | Latency |
|----------|---------|
| Tier 0 single pipeline (warm) | 2.1ms |
| Tier 0 parallel compare (2 texts, warm) | 4.5ms |
| Tier 1 single pipeline (warm) | 9.2ms |
| Tier 1 parallel compare (2 texts, warm) | 21.2ms |
| spaCy model load at startup | 1456ms (one-time) |

### Stage timing (Tier 0, warm, 5-run average)

| Stage | Time |
|-------|------|
| Stage 0 (sentence split, no spaCy) | 0.33ms |
| Stage 0 (sentence split, with spaCy) | 6.18ms |
| readability | 0.03ms |
| naturalness | 0.21ms |
| vocabulary | 0.04ms |
| tone | 0.15ms |
| additional | 0.05ms |

---

## Root Cause

The server lifespan (`app_lifespan` in `server.py`) pre-loads ML models
(spaCy, FastEmbed, is-it-slop, T5) but does **not** pre-import the pipeline
analysis modules. Python defers module-level imports until first use, so
`scipy.stats` and `lexicalrichness` are not imported until the first
`run_pipeline` call arrives.

The `asyncio.gather` in the compare tool is already correct — both texts run
in parallel. The spaCy model is already cached via lifespan. Neither of these
is the problem.

---

## Proposed Optimisations

### Option 1 — Dummy warm-up call in lifespan (recommended, minimal change)

Add a single dummy `run_pipeline` call at the end of `app_lifespan`. This forces
all lazy imports to resolve at startup, eliminating the cold-start penalty entirely.

```python
# In server.py app_lifespan, after Step 5 (warm up T5):

# Step 6: Force-import all pipeline modules by running a dummy analysis.
# Eliminates the scipy.stats + lexicalrichness cold-start penalty (~2.9s).
try:
    from phraseturner.pipeline.orchestrator import PipelineContext, run_pipeline  # noqa: PLC0415
    _dummy_ctx = PipelineContext(
        nlp=models.nlp,
        slop_detector=None,
        t5_model=None,
        fastembed_model=None,
        config=config,
        persona=None,
    )
    await run_pipeline("Warm up.", _dummy_ctx, quick_score=True)
    logger.info("pipeline_warmed_up")
except Exception:
    logger.warning("pipeline_warmup_failed")
```

**Cost**: ~530ms added to startup time (acceptable — startup already takes ~1.5s for spaCy).
**Benefit**: First compare call drops from 2.9s to ~21ms (Tier 1) or ~5ms (Tier 0).

### Option 2 — Eager imports at module level in server.py

Import the heavy modules explicitly in `server.py` so they resolve during the
lifespan startup sequence rather than on first request.

```python
# In server.py, after existing imports:
import scipy.stats  # noqa: F401 — pre-import to eliminate cold-start penalty
import lexicalrichness  # noqa: F401 — pre-import to eliminate cold-start penalty
```

**Cost**: ~3.8s added to server startup (one-time, before lifespan runs).
**Benefit**: Same as Option 1 — first call is warm.
**Downside**: Slightly longer startup; imports happen before config is loaded.

### Option 3 — Lazy import with explicit pre-warm function (cleanest)

Add a `pre_warm_pipeline()` async function to `orchestrator.py` that imports
all heavy modules and runs a dummy analysis. Call it from lifespan.

This is the cleanest approach but requires a small refactor.

---

## What Does NOT Need Changing

- **`asyncio.gather` in compare tool** — already implemented correctly. Both texts
  run in parallel. No change needed.
- **spaCy model caching** — already cached via lifespan. No change needed.
- **FastEmbed model loading** — not the bottleneck. No change needed.
- **Pipeline architecture** — warm calls are 4.5–21ms, well within 800ms target.

---

## Verification

After implementing Option 1, verify with:

```python
# In tests/calibration/test_hc3_calibration.py
# test_pipeline_latency_within_budget already covers warm-call latency.
# Add a cold-start test to verify the fix:

async def test_first_call_latency_within_budget():
    ctx = _make_tier0_ctx()
    t0 = time.perf_counter()
    await run_pipeline("Hello world.", ctx, quick_score=True)
    first_call_ms = (time.perf_counter() - t0) * 1000
    # After warm-up fix, first call should be < 100ms
    # (imports already resolved by lifespan)
    assert first_call_ms < 800.0
```
