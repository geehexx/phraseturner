"""Model loader managing spaCy, FastEmbed, is-it-slop, and FLAN-T5 ONNX models.

Provides async loading, tier detection, warm-up, and cleanup for all
optional ML models used by the phraseturner analysis pipeline.

Implements §5.1, §1.2.
Requirements: FR-T5-01, FR-T5-06.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from phraseturner.config import ServerConfig

logger: structlog.stdlib.BoundLogger = structlog.get_logger()


class ModelLoader:
    """Manages lifecycle of all ML models used by phraseturner.

    Each model is loaded asynchronously via ``asyncio.to_thread`` to avoid
    blocking the event loop.  Models that fail to load are logged and left
    as ``None`` — the server degrades gracefully to a lower operating tier.

    Implements §5.1 (Model Loading), §1.2 (5-Tier Operating Model).
    Requirements: FR-T5-01, FR-T5-06.
    """

    def __init__(self, config: ServerConfig) -> None:
        self._config = config
        self._nlp: Any = None
        self._fastembed: Any = None
        self._slop_detector: Any = None
        self._t5_session: Any = None
        self._t5_tokenizer: Any = None

    # ------------------------------------------------------------------
    # Properties — model accessors
    # ------------------------------------------------------------------

    @property
    def nlp(self) -> Any:
        """Return loaded spaCy ``Language`` model, or ``None``."""
        return self._nlp

    @property
    def fastembed(self) -> Any:
        """Return loaded FastEmbed ``TextEmbedding`` model, or ``None``."""
        return self._fastembed

    @property
    def slop_detector(self) -> Any:
        """Return loaded is-it-slop detector, or ``None``."""
        return self._slop_detector

    @property
    def t5_session(self) -> Any:
        """Return loaded ONNX ``InferenceSession`` for FLAN-T5, or ``None``."""
        return self._t5_session

    @property
    def t5_tokenizer(self) -> Any:
        """Return loaded T5 tokenizer, or ``None``."""
        return self._t5_tokenizer

    # ------------------------------------------------------------------
    # Availability flags
    # ------------------------------------------------------------------

    @property
    def spacy_available(self) -> bool:
        """Whether spaCy model is loaded (Tier 1+)."""
        return self._nlp is not None

    @property
    def fastembed_available(self) -> bool:
        """Whether FastEmbed model is loaded (Tier 4)."""
        return self._fastembed is not None

    @property
    def slop_available(self) -> bool:
        """Whether is-it-slop detector is loaded (Tier 2+)."""
        return self._slop_detector is not None

    @property
    def t5_available(self) -> bool:
        """Whether FLAN-T5 ONNX session is loaded (Tier 3+)."""
        return self._t5_session is not None and self._t5_tokenizer is not None

    # ------------------------------------------------------------------
    # Operating tier — §1.2
    # ------------------------------------------------------------------

    @property
    def operating_tier(self) -> int:
        """Compute operating tier (0-4) based on loaded models.

        Implements AC-FR-T5-06.1, AC-FR-T5-06.2, AC-FR-T5-06.3.

        Tier 0: textstat only (no spaCy).
        Tier 1: + spaCy en_core_web_sm.
        Tier 2: + is-it-slop.
        Tier 3: + FLAN-T5 ONNX INT8.
        Tier 4: + FastEmbed bge-small-en-v1.5.
        """
        if not self.spacy_available:
            return 0
        if not self.slop_available:
            return 1
        if not self.t5_available:
            return 2
        if not self.fastembed_available:
            return 3
        return 4

    # ------------------------------------------------------------------
    # Model version info
    # ------------------------------------------------------------------

    @property
    def model_versions(self) -> dict[str, str]:
        """Return version info for loaded models.

        Returns:
            Mapping of model name to version string.  Only includes
            models that are currently loaded.
        """
        versions: dict[str, str] = {}
        if self._nlp is not None:
            meta: dict[str, Any] = getattr(self._nlp, "meta", {})
            versions["spacy"] = str(meta.get("version", "unknown"))
        if self._t5_session is not None:
            versions["t5"] = "flan-t5-base-int8"
        if self._fastembed is not None:
            versions["fastembed"] = self._config.embed_model
        if self._slop_detector is not None:
            versions["is_it_slop"] = "0.5.0"
        return versions

    # ------------------------------------------------------------------
    # Async load methods
    # ------------------------------------------------------------------

    async def load_spacy(self) -> None:
        """Load spaCy language model in a background thread.

        Uses ``asyncio.to_thread`` since ``spacy.load()`` is CPU-bound.
        On failure, logs a warning — the server degrades to Tier 0.

        Implements AC-FR-T5-01.1.
        """
        model_name = self._config.spacy_model

        def _load() -> Any:
            import spacy  # noqa: PLC0415

            return spacy.load(model_name)

        try:
            self._nlp = await asyncio.to_thread(_load)
            logger.info("spacy_loaded", model=model_name)
        except Exception as exc:
            logger.warning(
                "spacy_load_failed",
                model=model_name,
                error=str(exc),
            )
            raise

    async def load_fastembed(self) -> None:
        """Load FastEmbed text embedding model in a background thread.

        Skipped when ``config.disable_embed`` is ``True``.
        On failure, logs a warning — the server degrades (no semantic search).

        Implements AC-FR-T5-01.1.
        """
        if self._config.disable_embed:
            logger.info("fastembed_disabled", reason="PHRASETURNER_DISABLE_EMBED=true")
            return

        model_name = self._config.embed_model

        def _load() -> Any:
            from fastembed import TextEmbedding  # noqa: PLC0415

            return TextEmbedding(model_name=model_name)

        try:
            self._fastembed = await asyncio.to_thread(_load)
            logger.info("fastembed_loaded", model=model_name)
        except Exception as exc:
            logger.warning(
                "fastembed_load_failed",
                model=model_name,
                error=str(exc),
            )

    async def load_slop_detector(self) -> None:
        """Load is-it-slop AI detection model in a background thread.

        Skipped when ``config.disable_slop`` is ``True``.
        On failure, logs a warning — the server falls back to stylometric detection.

        Implements AC-FR-T5-01.1.
        """
        if self._config.disable_slop:
            logger.info("slop_detector_disabled", reason="PHRASETURNER_DISABLE_SLOP=true")
            return

        def _load() -> Any:
            from is_it_slop import is_this_slop  # noqa: PLC0415

            # Wrap the function API in a simple object with a .score() method
            # so that ai_detection.py can call slop_detector.score(text).
            class _SlopWrapper:
                """Thin wrapper exposing is_this_slop as a .score() method."""

                @staticmethod
                def score(text: str) -> float:
                    result = is_this_slop(text)
                    return result.ai_probability

            return _SlopWrapper()

        try:
            self._slop_detector = await asyncio.to_thread(_load)
            logger.info("slop_detector_loaded")
        except Exception as exc:
            logger.warning(
                "slop_detector_load_failed",
                error=str(exc),
            )

    async def load_t5(self) -> None:
        """Load FLAN-T5-base INT8 ONNX model and tokenizer.

        Skipped when ``config.disable_t5`` is ``True``.
        Uses ``onnxruntime.InferenceSession`` with ``CPUExecutionProvider``.
        Model files are expected at ``config.model_dir``.

        Implements AC-FR-T5-01.2, AC-FR-T5-01.3, AC-FR-T5-01.4.
        """
        if self._config.disable_t5:
            logger.info("t5_disabled", reason="PHRASETURNER_DISABLE_T5=true")
            return

        model_dir = self._config.model_dir

        def _load() -> tuple[Any, Any]:
            import onnxruntime as ort  # noqa: PLC0415
            from transformers import AutoTokenizer  # noqa: PLC0415

            encoder_path = model_dir / "encoder_model_quantized.onnx"
            decoder_path = model_dir / "decoder_model_quantized.onnx"

            if not encoder_path.exists() or not decoder_path.exists():
                msg = (
                    f"FLAN-T5 ONNX model files not found at {model_dir}. "
                    "Run the model download command first."
                )
                raise FileNotFoundError(msg)

            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            # Load encoder + decoder sessions
            encoder_session = ort.InferenceSession(
                str(encoder_path),
                sess_options=sess_options,
                providers=["CPUExecutionProvider"],
            )
            decoder_session = ort.InferenceSession(
                str(decoder_path),
                sess_options=sess_options,
                providers=["CPUExecutionProvider"],
            )

            tokenizer = AutoTokenizer.from_pretrained(
                str(model_dir),
                local_files_only=True,
            )

            return (encoder_session, decoder_session), tokenizer

        try:
            sessions, tokenizer = await asyncio.to_thread(_load)
            self._t5_session = sessions
            self._t5_tokenizer = tokenizer
            logger.info("t5_loaded", model_dir=str(model_dir))
        except Exception as exc:
            logger.warning(
                "t5_load_failed",
                model_dir=str(model_dir),
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Warm-up — AC-FR-T5-01.5
    # ------------------------------------------------------------------

    async def warmup_t5(self) -> None:
        """Run a dummy inference to warm up the FLAN-T5 ONNX session.

        This pre-allocates internal buffers and avoids a cold-start
        penalty on the first real request.

        Implements AC-FR-T5-01.5.
        """
        if not self.t5_available:
            return

        def _warmup() -> None:
            import numpy as np  # noqa: PLC0415

            tokenizer = self._t5_tokenizer
            encoder_session, decoder_session = self._t5_session

            # Tokenize a short dummy input
            inputs = tokenizer(
                "classify: hello",
                return_tensors="np",
                max_length=32,
                truncation=True,
                padding="max_length",
            )

            input_ids: Any = inputs["input_ids"].astype(np.int64)
            attention_mask: Any = inputs["attention_mask"].astype(np.int64)

            # Run encoder
            encoder_outputs = encoder_session.run(
                None,
                {"input_ids": input_ids, "attention_mask": attention_mask},
            )

            # Run decoder with a single start token
            decoder_input_ids = np.array([[tokenizer.pad_token_id]], dtype=np.int64)
            decoder_session.run(
                None,
                {
                    "input_ids": decoder_input_ids,
                    "encoder_hidden_states": encoder_outputs[0],
                    "encoder_attention_mask": attention_mask,
                },
            )

        try:
            await asyncio.to_thread(_warmup)
            logger.info("t5_warmup_complete")
        except Exception as exc:
            logger.warning("t5_warmup_failed", error=str(exc))

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def cleanup(self) -> None:
        """Release all model resources.

        Sets all model references to ``None`` so the garbage collector
        can reclaim memory.
        """
        self._nlp = None
        self._fastembed = None
        self._slop_detector = None
        self._t5_session = None
        self._t5_tokenizer = None
        logger.info("models_cleaned_up")
