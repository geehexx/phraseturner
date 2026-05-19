"""Structured context builder, 512-token handling, and T5 inference runner.

Builds compact context packets (~126 tokens) from earlier pipeline stages
for FLAN-T5 prompts, handles 512-token input truncation, and provides
sequential ONNX inference via ``ThreadPoolExecutor(1)`` to work around
ONNX bug #21053.

Implements: AC-FR-T5-05.1 through AC-FR-T5-05.3, AC-FR-T5-07.1,
    AC-FR-T5-07.2
Design: §5.3, §5.6, §5.7
Requirements: FR-T5-05, FR-T5-07
"""

from __future__ import annotations

import asyncio
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_NEIGHBOR_TOKENS = 30
"""Maximum tokens for prev/next surrounding sentences. §5.3."""

_SUBWORD_EXPANSION_FACTOR = 1.3
"""Rough multiplier for whitespace tokens → subword tokens. §5.6."""

_MAX_T5_TOKENS = 512
"""FLAN-T5 input token limit. §5.6."""

_SHORT_THRESHOLD = 10
"""Sentences with fewer tokens are classified as 'short'."""

_LONG_THRESHOLD = 25
"""Sentences with more tokens are classified as 'long'."""

_VADER_POSITIVE_THRESHOLD = 0.05
"""VADER compound score above this is 'positive'."""

_VADER_NEGATIVE_THRESHOLD = -0.05
"""VADER compound score below this is 'negative'."""


# ---------------------------------------------------------------------------
# SentenceContext dataclass — §5.3
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SentenceContext:
    """Structured context packet for a single sentence.

    Contains surrounding sentences, derived parse signals, readability
    grade, length class, VADER label, AI signal, persona tone, and
    vocabulary hits.  Target overhead: ~126 tokens.

    Implements AC-FR-T5-05.1.

    Attributes:
        prev_sentence: Previous sentence truncated to ~30 tokens, or None.
        next_sentence: Next sentence truncated to ~30 tokens, or None.
        readability_grade: Readability grade for this sentence, or None.
        length_class: Sentence length classification — short/medium/long.
        vader_label: VADER sentiment — positive/negative/neutral, or None.
        ai_signal: AI detection signal — likely-ai/likely-human/uncertain.
        persona_tone: Target tone dimensions from persona, or None.
        avoid_hits: Prohibited vocabulary words found in the sentence.
        prefer_hits: Approved vocabulary words found in the sentence.
    """

    prev_sentence: str | None = None
    next_sentence: str | None = None
    readability_grade: float | None = None
    length_class: str = "medium"
    vader_label: str | None = None
    ai_signal: str | None = None
    persona_tone: dict[str, float] | None = None
    avoid_hits: list[str] = field(default_factory=list)
    prefer_hits: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to approximately *max_tokens* whitespace tokens.

    Args:
        text: Input text to truncate.
        max_tokens: Maximum number of whitespace-split tokens to keep.

    Returns:
        Truncated text (may be shorter than original).
    """
    words = text.split()
    if len(words) <= max_tokens:
        return text
    return " ".join(words[:max_tokens])


def _classify_length(sentence: str) -> str:
    """Classify sentence length as short, medium, or long.

    Args:
        sentence: The sentence text.

    Returns:
        Length class string: ``"short"`` (<10 tokens), ``"medium"``
        (10-25 tokens), or ``"long"`` (>25 tokens).
    """
    token_count = len(sentence.split())
    if token_count < _SHORT_THRESHOLD:
        return "short"
    if token_count > _LONG_THRESHOLD:
        return "long"
    return "medium"


def _vader_compound_to_label(compound: float) -> str:
    """Map a VADER compound score to a sentiment label.

    Args:
        compound: VADER compound score in range [-1.0, 1.0].

    Returns:
        Sentiment label: ``"positive"`` (>0.05), ``"negative"`` (<-0.05),
        or ``"neutral"``.
    """
    if compound > _VADER_POSITIVE_THRESHOLD:
        return "positive"
    if compound < _VADER_NEGATIVE_THRESHOLD:
        return "negative"
    return "neutral"


def _estimate_subword_tokens(text: str) -> int:
    """Estimate subword token count from whitespace token count.

    Uses a rough 1.3x expansion factor per §5.6.

    Args:
        text: Input text.

    Returns:
        Estimated subword token count.
    """
    word_count = len(text.split())
    return math.ceil(word_count * _SUBWORD_EXPANSION_FACTOR)


# ---------------------------------------------------------------------------
# build_context — §5.3
# ---------------------------------------------------------------------------


def _extract_persona_signals(
    persona: Any,
    sentence: str,
) -> tuple[dict[str, float] | None, list[str], list[str]]:
    """Extract persona tone targets and vocabulary hits for a sentence.

    Args:
        persona: PersonaConfig with tone and vocabulary attributes.
        sentence: The sentence text to check for vocabulary hits.

    Returns:
        Tuple of (persona_tone dict, avoid_hits list, prefer_hits list).
    """
    persona_tone: dict[str, float] | None = None
    avoid_hits: list[str] = []
    prefer_hits: list[str] = []

    tone_cfg = getattr(persona, "tone", None)
    if tone_cfg is not None:
        persona_tone = {
            "formality": tone_cfg.formality,
            "confidence": tone_cfg.confidence,
            "warmth": tone_cfg.warmth,
            "directness": tone_cfg.directness,
            "energy": tone_cfg.energy,
            "verbosity": tone_cfg.verbosity,
        }

    vocab_cfg = getattr(persona, "vocabulary", None)
    if vocab_cfg is not None:
        sentence_lower = sentence.lower()
        for word in vocab_cfg.prohibited:
            if word.lower() in sentence_lower:
                avoid_hits.append(word)
        for word in vocab_cfg.approved:
            if word.lower() in sentence_lower:
                prefer_hits.append(word)

    return persona_tone, avoid_hits, prefer_hits


def build_context(  # noqa: PLR0913
    sentence_idx: int,
    sentences: list[str],
    *,
    readability_grades: list[float] | None = None,
    vader_compounds: list[float] | None = None,
    ai_signal: str | None = None,
    persona: Any = None,
) -> SentenceContext:
    """Build a structured context packet for a sentence.

    Implements AC-FR-T5-05.1, AC-FR-T5-05.3.

    Args:
        sentence_idx: Index of the target sentence in *sentences*.
        sentences: All sentences from the input text.
        readability_grades: Per-sentence readability grades, or None.
        vader_compounds: Per-sentence VADER compound scores, or None.
        ai_signal: AI detection signal for the whole text.
        persona: Optional ``PersonaConfig`` for tone and vocabulary.

    Returns:
        A ``SentenceContext`` packet ready for prompt formatting.
    """
    sentence = sentences[sentence_idx]

    prev_sentence: str | None = None
    next_sentence: str | None = None
    if sentence_idx > 0:
        prev_sentence = _truncate_to_tokens(sentences[sentence_idx - 1], _MAX_NEIGHBOR_TOKENS)
    if sentence_idx < len(sentences) - 1:
        next_sentence = _truncate_to_tokens(sentences[sentence_idx + 1], _MAX_NEIGHBOR_TOKENS)

    readability_grade: float | None = None
    if readability_grades is not None and sentence_idx < len(readability_grades):
        readability_grade = readability_grades[sentence_idx]

    vader_label: str | None = None
    if vader_compounds is not None and sentence_idx < len(vader_compounds):
        vader_label = _vader_compound_to_label(vader_compounds[sentence_idx])

    persona_tone: dict[str, float] | None = None
    avoid_hits: list[str] = []
    prefer_hits: list[str] = []
    if persona is not None:
        persona_tone, avoid_hits, prefer_hits = _extract_persona_signals(persona, sentence)

    return SentenceContext(
        prev_sentence=prev_sentence,
        next_sentence=next_sentence,
        readability_grade=readability_grade,
        length_class=_classify_length(sentence),
        vader_label=vader_label,
        ai_signal=ai_signal,
        persona_tone=persona_tone,
        avoid_hits=avoid_hits,
        prefer_hits=prefer_hits,
    )


# ---------------------------------------------------------------------------
# format_context_string — §5.3
# ---------------------------------------------------------------------------


def format_context_string(ctx: SentenceContext) -> str:
    """Format a ``SentenceContext`` into a compact string for T5 prompts.

    Produces a human-readable context string targeting ~126 tokens that
    can be prepended to FLAN-T5 prompt templates.

    Implements AC-FR-T5-05.2.

    Args:
        ctx: The structured context packet.

    Returns:
        Compact context string suitable for T5 input.
    """
    parts: list[str] = []

    # Surrounding sentences (~70 tokens)
    if ctx.prev_sentence:
        parts.append(f"prev: {ctx.prev_sentence}")
    if ctx.next_sentence:
        parts.append(f"next: {ctx.next_sentence}")

    # Metrics (~18 tokens)
    if ctx.readability_grade is not None:
        parts.append(f"grade: {ctx.readability_grade:.1f}")
    parts.append(f"length: {ctx.length_class}")

    # Derived signals (~16 tokens)
    if ctx.vader_label:
        parts.append(f"sentiment: {ctx.vader_label}")
    if ctx.ai_signal:
        parts.append(f"ai: {ctx.ai_signal}")

    # Persona tone (~12 tokens)
    if ctx.persona_tone:
        tone_parts = [f"{k}={v:.1f}" for k, v in ctx.persona_tone.items()]
        parts.append(f"tone: {', '.join(tone_parts)}")

    # Avoid/prefer hits (~10 tokens)
    if ctx.avoid_hits:
        parts.append(f"avoid: {', '.join(ctx.avoid_hits[:5])}")
    if ctx.prefer_hits:
        parts.append(f"prefer: {', '.join(ctx.prefer_hits[:5])}")

    return " | ".join(parts)


# ---------------------------------------------------------------------------
# truncate_for_t5 — §5.6
# ---------------------------------------------------------------------------


def truncate_for_t5(
    sentence: str,
    context_string: str,
    max_tokens: int = _MAX_T5_TOKENS,
) -> tuple[str, bool]:
    """Truncate a sentence to fit within the T5 input token limit.

    Estimates token count using whitespace splitting with a 1.3x subword
    expansion factor.  When context + sentence exceeds *max_tokens*,
    truncates the sentence from the end, preserving the beginning.

    Implements AC-FR-T5-07.1, AC-FR-T5-07.2.

    Args:
        sentence: The sentence text to potentially truncate.
        context_string: The formatted context string that will be
            prepended to the prompt.
        max_tokens: Maximum total token budget (default 512).

    Returns:
        Tuple of (possibly truncated sentence, was_truncated flag).
    """
    context_tokens = _estimate_subword_tokens(context_string)
    sentence_tokens = _estimate_subword_tokens(sentence)

    if context_tokens + sentence_tokens <= max_tokens:
        return sentence, False

    # Budget remaining for the sentence after context
    available = max_tokens - context_tokens
    if available <= 0:
        # Context alone exceeds budget — return minimal sentence
        words = sentence.split(maxsplit=1)
        return words[0] if words else "", True

    # Convert available subword tokens back to approximate word count
    available_words = int(available / _SUBWORD_EXPANSION_FACTOR)
    words = sentence.split()

    if available_words >= len(words):
        return sentence, False

    truncated = " ".join(words[:available_words])
    return truncated, True


# ---------------------------------------------------------------------------
# T5Runner — §5.7
# ---------------------------------------------------------------------------


class T5Runner:
    """Sequential ONNX inference runner for FLAN-T5.

    Uses ``ThreadPoolExecutor(max_workers=1)`` and ``asyncio.to_thread``
    to run inference sequentially, working around ONNX bug #21053 which
    causes incorrect results with concurrent session access.

    Implements §5.7 (Batching: batch_size=1, sequential).

    Attributes:
        _encoder_session: ONNX encoder inference session.
        _decoder_session: ONNX decoder inference session.
        _tokenizer: HuggingFace tokenizer for FLAN-T5.
        _executor: Single-threaded executor for sequential inference.
    """

    def __init__(self, session: Any, tokenizer: Any) -> None:
        """Initialise the T5 runner.

        Args:
            session: Tuple of (encoder_session, decoder_session) from
                ``ModelLoader.t5_session``.
            tokenizer: HuggingFace tokenizer from
                ``ModelLoader.t5_tokenizer``.
        """
        self._encoder_session, self._decoder_session = session
        self._tokenizer = tokenizer
        self._executor = ThreadPoolExecutor(max_workers=1)

    async def run_task(
        self,
        prompt: str,
        max_tokens: int,
        use_beam: bool,
    ) -> tuple[str, float]:
        """Run a single T5 inference task asynchronously.

        Delegates to the single-threaded executor to ensure sequential
        access to the ONNX sessions (batch_size=1 per ONNX bug #21053).

        Args:
            prompt: The formatted prompt string.
            max_tokens: Maximum output tokens for generation.
            use_beam: Whether to use beam search (True) or greedy (False).

        Returns:
            Tuple of (decoded output text, confidence score).
            Confidence is 1.0 for greedy decoding.
        """
        return await asyncio.to_thread(self._infer, prompt, max_tokens, use_beam)

    def _infer(
        self,
        prompt: str,
        max_tokens: int,
        use_beam: bool,
    ) -> tuple[str, float]:
        """Synchronous inference. batch_size=1 per ONNX bug #21053.

        Tokenizes the prompt, runs the encoder, then autoregressively
        decodes using either greedy or beam search.

        Args:
            prompt: The formatted prompt string.
            max_tokens: Maximum output tokens for generation.
            use_beam: Whether to use beam search for confidence scoring.

        Returns:
            Tuple of (decoded text, confidence score).
        """
        # Tokenize input — FR-T5-07 (512 token limit handled upstream)
        inputs = self._tokenizer(
            prompt,
            return_tensors="np",
            max_length=_MAX_T5_TOKENS,
            truncation=True,
            padding="max_length",
        )

        input_ids = inputs["input_ids"].astype(np.int64)
        attention_mask = inputs["attention_mask"].astype(np.int64)

        # Run encoder
        encoder_outputs = self._encoder_session.run(
            None,
            {"input_ids": input_ids, "attention_mask": attention_mask},
        )
        encoder_hidden = encoder_outputs[0]

        if use_beam:
            return self._beam_search_decode(encoder_hidden, attention_mask, max_tokens)
        return self._greedy_decode(encoder_hidden, attention_mask, max_tokens)

    def _greedy_decode(
        self,
        encoder_hidden: Any,
        attention_mask: Any,
        max_tokens: int,
    ) -> tuple[str, float]:
        """Greedy decoding for deterministic output.

        Args:
            encoder_hidden: Encoder hidden states.
            attention_mask: Encoder attention mask.
            max_tokens: Maximum output tokens.

        Returns:
            Tuple of (decoded text, confidence=1.0).
        """
        pad_id = self._tokenizer.pad_token_id
        eos_id = self._tokenizer.eos_token_id

        decoder_ids = [pad_id]

        for _ in range(max_tokens):
            decoder_input = np.array([decoder_ids], dtype=np.int64)
            outputs = self._decoder_session.run(
                None,
                {
                    "input_ids": decoder_input,
                    "encoder_hidden_states": encoder_hidden,
                    "encoder_attention_mask": attention_mask,
                },
            )
            logits = outputs[0]
            next_token = int(np.argmax(logits[0, -1, :]))

            if next_token == eos_id:
                break
            decoder_ids.append(next_token)

        # Skip the initial pad token
        output_ids = decoder_ids[1:]
        text = self._tokenizer.decode(output_ids, skip_special_tokens=True)
        return text.strip(), 1.0

    def _expand_beam(
        self,
        token_ids: list[int],
        cum_log_prob: float,
        encoder_hidden: Any,
        attention_mask: Any,
        num_beams: int,
    ) -> tuple[list[tuple[list[int], float]], list[tuple[list[int], float]]]:
        """Expand a single beam into candidate and completed sequences.

        Returns:
            Tuple of (new_candidates, new_completed).
        """
        eos_id = self._tokenizer.eos_token_id
        decoder_input = np.array([token_ids], dtype=np.int64)
        outputs = self._decoder_session.run(
            None,
            {
                "input_ids": decoder_input,
                "encoder_hidden_states": encoder_hidden,
                "encoder_attention_mask": attention_mask,
            },
        )
        logits = outputs[0][0, -1, :]

        max_logit = float(np.max(logits))
        exp_logits = np.exp(logits - max_logit)
        probs = exp_logits / np.sum(exp_logits)
        top_indices = np.argsort(probs)[-num_beams:]

        candidates: list[tuple[list[int], float]] = []
        completed: list[tuple[list[int], float]] = []
        for idx in top_indices:
            token = int(idx)
            log_prob = float(np.log(probs[token] + 1e-10))
            new_ids = [*token_ids, token]
            new_score = cum_log_prob + log_prob
            if token == eos_id:
                completed.append((new_ids, new_score))
            else:
                candidates.append((new_ids, new_score))
        return candidates, completed

    def _select_best_sequence(
        self,
        all_sequences: list[tuple[list[int], float]],
    ) -> tuple[str, float]:
        """Select the best beam sequence and decode to text with confidence.

        Returns:
            Tuple of (decoded text, confidence score in [0, 1]).
        """
        if not all_sequences:
            return "", 0.0

        eos_id = self._tokenizer.eos_token_id
        all_sequences.sort(key=lambda x: x[1], reverse=True)
        best_ids, best_score = all_sequences[0]

        output_ids = [t for t in best_ids[1:] if t != eos_id]
        text = self._tokenizer.decode(output_ids, skip_special_tokens=True)

        seq_len = max(len(output_ids), 1)
        confidence = float(np.exp(best_score / seq_len))
        confidence = max(0.0, min(1.0, confidence))
        return text.strip(), confidence

    def _beam_search_decode(
        self,
        encoder_hidden: Any,
        attention_mask: Any,
        max_tokens: int,
        num_beams: int = 4,
    ) -> tuple[str, float]:
        """Beam search decoding with softmax confidence scoring.

        Args:
            encoder_hidden: Encoder hidden states.
            attention_mask: Encoder attention mask.
            max_tokens: Maximum output tokens.
            num_beams: Number of beams (default 4 per §5.2).

        Returns:
            Tuple of (decoded text, confidence score in [0, 1]).
        """
        pad_id = self._tokenizer.pad_token_id
        beams: list[tuple[list[int], float]] = [([pad_id], 0.0)]
        completed: list[tuple[list[int], float]] = []

        for _ in range(max_tokens):
            candidates: list[tuple[list[int], float]] = []
            for token_ids, cum_log_prob in beams:
                new_cands, new_done = self._expand_beam(
                    token_ids,
                    cum_log_prob,
                    encoder_hidden,
                    attention_mask,
                    num_beams,
                )
                candidates.extend(new_cands)
                completed.extend(new_done)

            if not candidates:
                break
            candidates.sort(key=lambda x: x[1], reverse=True)
            beams = candidates[:num_beams]
            if len(completed) >= num_beams:
                break

        return self._select_best_sequence(completed + beams)

    async def cleanup(self) -> None:
        """Shut down the executor.

        Releases the thread pool without waiting for pending tasks.
        """
        self._executor.shutdown(wait=False)
