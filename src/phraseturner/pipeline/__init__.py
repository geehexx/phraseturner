"""Analysis pipeline stages for phraseturner.

Implements the 6-stage analysis pipeline (§4.1):
Stage 0 — Input validation and sentence splitting
Stage 1 — Classical NLP analyzers (parallel)
Stage 2 — AI detection
Stage 3 — FLAN-T5 deep analysis
Stage 4 — Score aggregation
Stage 5 — Output formatting
"""

from __future__ import annotations

from phraseturner.pipeline.formatting import (
    compute_persona_alignment,
    format_output,
    generate_flags,
    generate_suggestions,
)
from phraseturner.pipeline.orchestrator import (
    PipelineContext,
    run_pipeline,
)

__all__ = [
    "PipelineContext",
    "compute_persona_alignment",
    "format_output",
    "generate_flags",
    "generate_suggestions",
    "run_pipeline",
]
