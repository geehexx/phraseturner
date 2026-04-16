"""Server configuration via PHRASETURNER_* environment variables.

Implements: AC-FR-PERSONA-09.1, AC-FR-PERSONA-09.2, AC-FR-T5-01.4,
            AC-FR-T5-01.5, AC-NFR-DIST-04.4
Design: §1.4
"""

# Tests that override PHRASETURNER_* env vars must call get_config.cache_clear()
# before setting env vars to avoid stale cached config.

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class ServerConfig(BaseSettings):
    """Server configuration via PHRASETURNER_* environment variables.

    All fields are configurable via ``PHRASETURNER_<FIELD>`` env vars
    (e.g. ``PHRASETURNER_DISABLE_T5=true``).
    """

    model_config = {"env_prefix": "PHRASETURNER_"}

    # Persona directories — AC-FR-PERSONA-09.1
    personas_dir: Path | None = None

    # Model toggles
    disable_t5: bool = False        # FR-T5-01.4
    disable_slop: bool = False
    disable_embed: bool = False

    # Model paths — NFR-DIST-04
    model_dir: Path = Path("~/.cache/phraseturner/models/").expanduser()
    embed_model: str = "BAAI/bge-small-en-v1.5"
    spacy_model: str = "en_core_web_sm"

    # Analysis limits
    max_tokens: int = 8_000         # FR-TOOL-01.7
    max_sentences_t5: int = 20

    # Hot-reload — FR-PERSONA-04.2
    watch_enabled: bool = True
    watch_debounce_ms: int = 500

    # Logging
    log_level: str = "INFO"


@lru_cache
def get_config() -> ServerConfig:
    """Return cached server configuration singleton."""
    return ServerConfig()
