"""Stage 0: Input validation and sentence splitting.

Tokenise with spaCy, reject if >8000 tokens (``TEXT_TOO_LONG``),
reject empty/whitespace (``TEXT_TOO_SHORT``), split into sentences
via spaCy sentencizer.

Implements §4.2.
Requirements: FR-PIPELINE-01, NFR-SEC-01.
"""

from __future__ import annotations

import asyncio
import dataclasses
import re
from typing import TYPE_CHECKING

from phraseturner.exceptions import TextTooLongError, TextTooShortError

if TYPE_CHECKING:
    from spacy.language import Language
    from spacy.tokens import Doc

    from phraseturner.config import ServerConfig


@dataclasses.dataclass(frozen=True)
class Stage0Result:
    """Result of Stage 0: input validation and sentence splitting.

    Attributes:
        doc: The spaCy ``Doc`` produced by the language model (``None``
            when running in Tier 0 fallback mode).
        sentences: Sentence texts extracted from the input.
        token_count: Number of non-whitespace tokens in the input.
    """

    doc: Doc | None
    sentences: list[str]
    token_count: int


# ---------------------------------------------------------------------------
# Tier 0 fallback helpers (no spaCy available)
# ---------------------------------------------------------------------------

_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")


def _fallback_split_sentences(text: str) -> list[str]:
    """Split text into sentences using regex when spaCy is unavailable.

    A simple heuristic: split on whitespace following sentence-ending
    punctuation (``.``, ``!``, ``?``).
    """
    parts = _SENTENCE_BOUNDARY_RE.split(text)
    return [p.strip() for p in parts if p.strip()]


def _fallback_token_count(text: str) -> int:
    """Count tokens by whitespace splitting when spaCy is unavailable."""
    return len(text.split())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def run_stage0(
    text: str,
    nlp: Language | None,
    config: ServerConfig,
) -> Stage0Result:
    """Validate input text and split into sentences. Implements §4.2.

    Args:
        text: Raw input text to validate and split.
        nlp: Loaded spaCy ``Language`` model, or ``None`` for Tier 0
            fallback.
        config: Server configuration (for ``max_tokens``).

    Returns:
        Stage0Result with doc, sentences, and token count.

    Raises:
        TextTooShortError: If text is empty or whitespace only.
        TextTooLongError: If text exceeds ``config.max_tokens``.
    """
    # 1. Reject empty / whitespace-only input — AC-NFR-SEC-01.1
    stripped = text.strip()
    if not stripped:
        raise TextTooShortError(
            "Input text is empty or contains only whitespace.",
        )

    # 2. Tier 0 fallback: no spaCy model available
    if nlp is None:
        token_count = _fallback_token_count(stripped)
        if token_count > config.max_tokens:
            raise TextTooLongError(
                f"Input text has {token_count} tokens, exceeding the {config.max_tokens} limit.",
                details={"token_count": token_count, "max_tokens": config.max_tokens},
            )
        sentences = _fallback_split_sentences(stripped)
        return Stage0Result(doc=None, sentences=sentences, token_count=token_count)

    # 3. Process with spaCy (CPU-bound → offload to thread)
    doc: Doc = await asyncio.to_thread(nlp, stripped)

    # 4. Count non-whitespace tokens — AC-FR-TOOL-01.7
    token_count = sum(1 for tok in doc if not tok.is_space)

    # 5. Reject if over limit
    if token_count > config.max_tokens:
        raise TextTooLongError(
            f"Input text has {token_count} tokens, exceeding the {config.max_tokens} limit.",
            details={"token_count": token_count, "max_tokens": config.max_tokens},
        )

    # 6. Split into sentences via spaCy sentence boundary detection
    sentences = [sent.text for sent in doc.sents]

    return Stage0Result(doc=doc, sentences=sentences, token_count=token_count)
