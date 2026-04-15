"""Model download utilities for first-run setup.

Downloads FLAN-T5 ONNX INT8 and spaCy models on first run.
Models are cached locally and skipped on subsequent runs.

Implements §8.3.
Requirements: NFR-DIST-04.
"""

from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from pathlib import Path

    from phraseturner.config import ServerConfig

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

# Default HuggingFace repo for the quantized FLAN-T5-base ONNX model.
# Override via ``PHRASETURNER_T5_REPO_ID`` if hosting a custom model.
_DEFAULT_T5_REPO_ID = "AdrianCrozier/flan-t5-base-onnx-int8"

# Files that must be present for the T5 model to be considered cached.
_T5_REQUIRED_FILES = frozenset(
    {
        "encoder_model_quantized.onnx",
        "decoder_model_quantized.onnx",
        "tokenizer.json",
        "config.json",
    }
)


def _log_stderr(message: str) -> None:
    """Write a progress message to stderr.

    Args:
        message: Human-readable progress string.
    """
    sys.stderr.write(f"[phraseturner] {message}\n")
    sys.stderr.flush()


async def ensure_spacy_model(model_name: str = "en_core_web_sm") -> None:
    """Download spaCy language model if not already installed.

    Checks ``spacy.util.is_package`` first and skips the download when
    the model is already available.  Progress is logged to stderr.

    Args:
        model_name: spaCy model package name.

    Implements AC-NFR-DIST-04.2, AC-NFR-DIST-04.3.
    """

    def _check_and_download() -> bool:
        import spacy.util  # noqa: PLC0415

        if spacy.util.is_package(model_name):
            return False  # already installed

        _log_stderr(f"Downloading spaCy model '{model_name}' ...")
        import spacy.cli  # noqa: PLC0415

        spacy.cli.download(model_name)  # type: ignore[attr-defined]
        _log_stderr(f"spaCy model '{model_name}' downloaded successfully.")
        return True

    downloaded = await asyncio.to_thread(_check_and_download)
    if downloaded:
        logger.info("spacy_model_downloaded", model=model_name)
    else:
        logger.debug("spacy_model_cached", model=model_name)


async def ensure_t5_model(model_dir: Path) -> Path:
    """Download FLAN-T5 ONNX INT8 model files if not already cached.

    Uses ``huggingface_hub.snapshot_download`` to fetch the model
    repository into *model_dir*.  Skips the download when all required
    files are already present.

    Args:
        model_dir: Local directory for model storage.

    Returns:
        Path to the directory containing the model files.

    Implements AC-NFR-DIST-04.1, AC-NFR-DIST-04.2, AC-NFR-DIST-04.3,
               AC-NFR-DIST-04.4.
    """
    model_dir.mkdir(parents=True, exist_ok=True)

    # Check whether all required files are already cached.
    existing = {f.name for f in model_dir.iterdir() if f.is_file()}
    if _T5_REQUIRED_FILES.issubset(existing):
        logger.debug("t5_model_cached", model_dir=str(model_dir))
        return model_dir

    missing = _T5_REQUIRED_FILES - existing
    _log_stderr(f"Downloading FLAN-T5 ONNX INT8 model (~220 MB) to {model_dir} ...")
    logger.info(
        "t5_model_download_starting",
        model_dir=str(model_dir),
        missing_files=sorted(missing),
    )

    def _download() -> None:
        from huggingface_hub import snapshot_download  # noqa: PLC0415

        snapshot_download(
            repo_id=_DEFAULT_T5_REPO_ID,
            local_dir=str(model_dir),
        )

    await asyncio.to_thread(_download)

    # Verify download succeeded.
    post_download = {f.name for f in model_dir.iterdir() if f.is_file()}
    still_missing = _T5_REQUIRED_FILES - post_download
    if still_missing:
        msg = (
            f"T5 model download incomplete — missing files: {sorted(still_missing)}. "
            f"Check the HuggingFace repo '{_DEFAULT_T5_REPO_ID}'."
        )
        raise FileNotFoundError(msg)

    _log_stderr("FLAN-T5 ONNX INT8 model downloaded successfully.")
    logger.info("t5_model_downloaded", model_dir=str(model_dir))
    return model_dir


async def ensure_all_models(config: ServerConfig) -> None:
    """Orchestrate downloading all required models.

    Calls :func:`ensure_spacy_model` and, unless T5 is disabled,
    :func:`ensure_t5_model`.  Logs a summary of what was downloaded
    versus what was already cached.

    Args:
        config: Server configuration providing model paths and toggles.

    Implements AC-NFR-DIST-04.2, AC-NFR-DIST-04.3.
    """
    downloaded: list[str] = []
    cached: list[str] = []

    # --- spaCy model ---------------------------------------------------
    def _spacy_is_cached() -> bool:
        import spacy.util  # noqa: PLC0415

        return spacy.util.is_package(config.spacy_model)

    spacy_cached = await asyncio.to_thread(_spacy_is_cached)
    await ensure_spacy_model(config.spacy_model)
    (cached if spacy_cached else downloaded).append(f"spacy:{config.spacy_model}")

    # --- FLAN-T5 ONNX --------------------------------------------------
    if not config.disable_t5:
        existing_before = (
            {f.name for f in config.model_dir.iterdir() if f.is_file()}
            if config.model_dir.exists()
            else set()
        )
        t5_was_cached = _T5_REQUIRED_FILES.issubset(existing_before)

        await ensure_t5_model(config.model_dir)
        (cached if t5_was_cached else downloaded).append("flan-t5-base-int8")
    else:
        logger.info("t5_download_skipped", reason="PHRASETURNER_DISABLE_T5=true")

    # --- Summary --------------------------------------------------------
    logger.info(
        "model_download_summary",
        downloaded=downloaded or ["none"],
        cached=cached or ["none"],
    )
    if downloaded:
        _log_stderr(f"Models downloaded: {', '.join(downloaded)}")
    if cached:
        _log_stderr(f"Models already cached: {', '.join(cached)}")
