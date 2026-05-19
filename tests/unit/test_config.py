"""Tests for phraseturner.config — ServerConfig and get_config singleton.

Validates: NFR-QUAL-04.
"""

from __future__ import annotations

from pathlib import Path

import pytest  # noqa: TC002

from phraseturner.config import ServerConfig, get_config


class TestServerConfigDefaults:
    """ServerConfig fields have correct default values."""

    def test_personas_dir_default_none(self) -> None:
        cfg = ServerConfig()
        assert cfg.personas_dir is None

    def test_disable_t5_default_false(self) -> None:
        cfg = ServerConfig()
        assert cfg.disable_t5 is False

    def test_disable_slop_default_false(self) -> None:
        cfg = ServerConfig()
        assert cfg.disable_slop is False

    def test_disable_embed_default_false(self) -> None:
        cfg = ServerConfig()
        assert cfg.disable_embed is False

    def test_model_dir_default(self) -> None:
        cfg = ServerConfig()
        assert cfg.model_dir == Path("~/.cache/phraseturner/models/").expanduser()

    def test_embed_model_default(self) -> None:
        cfg = ServerConfig()
        assert cfg.embed_model == "BAAI/bge-small-en-v1.5"

    def test_spacy_model_default(self) -> None:
        cfg = ServerConfig()
        assert cfg.spacy_model == "en_core_web_sm"

    def test_max_tokens_default(self) -> None:
        cfg = ServerConfig()
        assert cfg.max_tokens == 8_000

    def test_max_sentences_t5_default(self) -> None:
        cfg = ServerConfig()
        assert cfg.max_sentences_t5 == 20

    def test_watch_enabled_default(self) -> None:
        cfg = ServerConfig()
        assert cfg.watch_enabled is True

    def test_watch_debounce_ms_default(self) -> None:
        cfg = ServerConfig()
        assert cfg.watch_debounce_ms == 500

    def test_log_level_default(self) -> None:
        cfg = ServerConfig()
        assert cfg.log_level == "INFO"


class TestServerConfigEnvOverrides:
    """Environment variables override ServerConfig defaults."""

    def test_disable_t5_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PHRASETURNER_DISABLE_T5", "true")
        cfg = ServerConfig()
        assert cfg.disable_t5 is True

    def test_max_tokens_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PHRASETURNER_MAX_TOKENS", "4000")
        cfg = ServerConfig()
        assert cfg.max_tokens == 4000

    def test_log_level_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PHRASETURNER_LOG_LEVEL", "DEBUG")
        cfg = ServerConfig()
        assert cfg.log_level == "DEBUG"

    def test_personas_dir_env(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setenv("PHRASETURNER_PERSONAS_DIR", str(tmp_path))
        cfg = ServerConfig()
        assert cfg.personas_dir == tmp_path

    def test_watch_debounce_ms_env(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("PHRASETURNER_WATCH_DEBOUNCE_MS", "1000")
        cfg = ServerConfig()
        assert cfg.watch_debounce_ms == 1000


class TestGetConfigLruCache:
    """get_config() returns a cached singleton."""

    def test_returns_server_config(self) -> None:
        get_config.cache_clear()
        cfg = get_config()
        assert isinstance(cfg, ServerConfig)

    def test_same_instance_on_repeated_calls(self) -> None:
        get_config.cache_clear()
        first = get_config()
        second = get_config()
        assert first is second

    def test_cache_clear_produces_new_instance(self) -> None:
        get_config.cache_clear()
        first = get_config()
        get_config.cache_clear()
        second = get_config()
        assert first is not second

    def test_env_override_after_cache_clear(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        get_config.cache_clear()
        monkeypatch.setenv("PHRASETURNER_LOG_LEVEL", "WARNING")
        cfg = get_config()
        assert cfg.log_level == "WARNING"
        get_config.cache_clear()
