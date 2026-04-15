"""Targeted tests to close coverage gaps in modules below 80%.

Covers:
- __main__.py: entry point importability and main() function
- models/loader.py: model loading success/error paths with mocks
- server.py: app_lifespan context manager
- t5/context.py: T5Runner inference methods (greedy + beam search)
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from phraseturner.config import ServerConfig
from phraseturner.models.loader import ModelLoader


# ---------------------------------------------------------------------------
# __main__.py coverage
# ---------------------------------------------------------------------------
class TestMainModule:
    """Tests for __main__.py entry point."""

    def test_main_function_exists(self) -> None:
        """Verify main() is importable."""
        from phraseturner.__main__ import main
        assert callable(main)

    def test_main_calls_mcp_run(self) -> None:
        """Verify main() calls mcp.run()."""
        with patch("phraseturner.__main__.mcp") as mock_mcp:
            from phraseturner.__main__ import main
            main()
            mock_mcp.run.assert_called_once()


# ---------------------------------------------------------------------------
# models/loader.py — load_fastembed success path (lines 187-198)
# ---------------------------------------------------------------------------
class TestLoaderFastembedSuccess:
    """Tests for ModelLoader.load_fastembed() success path."""

    @pytest.mark.asyncio
    async def test_load_fastembed_success(self) -> None:
        """load_fastembed stores the model when loading succeeds."""
        config = ServerConfig(disable_embed=False, disable_t5=True, disable_slop=True)
        loader = ModelLoader(config)
        mock_model = MagicMock()
        with patch(
            "phraseturner.models.loader.asyncio.to_thread",
            return_value=mock_model,
        ):
            await loader.load_fastembed()
        assert loader.fastembed_available
        assert loader.fastembed is mock_model

    @pytest.mark.asyncio
    async def test_load_fastembed_failure_graceful(self) -> None:
        """load_fastembed logs warning on failure, does not raise."""
        config = ServerConfig(disable_embed=False, disable_t5=True, disable_slop=True)
        loader = ModelLoader(config)
        with patch(
            "phraseturner.models.loader.asyncio.to_thread",
            side_effect=ImportError("fastembed not installed"),
        ):
            await loader.load_fastembed()
        assert not loader.fastembed_available


# ---------------------------------------------------------------------------
# models/loader.py — load_slop_detector success path (lines 216-235)
# ---------------------------------------------------------------------------
class TestLoaderSlopSuccess:
    """Tests for ModelLoader.load_slop_detector() success path."""

    @pytest.mark.asyncio
    async def test_load_slop_detector_success(self) -> None:
        """load_slop_detector stores the wrapper when loading succeeds."""
        config = ServerConfig(disable_slop=False, disable_t5=True, disable_embed=True)
        loader = ModelLoader(config)
        mock_wrapper = MagicMock()
        with patch(
            "phraseturner.models.loader.asyncio.to_thread",
            return_value=mock_wrapper,
        ):
            await loader.load_slop_detector()
        assert loader.slop_available
        assert loader.slop_detector is mock_wrapper

    @pytest.mark.asyncio
    async def test_load_slop_detector_failure_graceful(self) -> None:
        """load_slop_detector logs warning on failure, does not raise."""
        config = ServerConfig(disable_slop=False, disable_t5=True, disable_embed=True)
        loader = ModelLoader(config)
        with patch(
            "phraseturner.models.loader.asyncio.to_thread",
            side_effect=ImportError("is_it_slop not installed"),
        ):
            await loader.load_slop_detector()
        assert not loader.slop_available


# ---------------------------------------------------------------------------
# models/loader.py — load_t5 success/error paths (lines 253-297)
# ---------------------------------------------------------------------------
class TestLoaderT5:
    """Tests for ModelLoader.load_t5() success and error paths."""

    @pytest.mark.asyncio
    async def test_load_t5_success(self) -> None:
        """load_t5 stores session and tokenizer when loading succeeds."""
        config = ServerConfig(disable_t5=False, disable_slop=True, disable_embed=True)
        loader = ModelLoader(config)
        mock_sessions = (MagicMock(), MagicMock())
        mock_tokenizer = MagicMock()
        with patch(
            "phraseturner.models.loader.asyncio.to_thread",
            return_value=(mock_sessions, mock_tokenizer),
        ):
            await loader.load_t5()
        assert loader.t5_available
        assert loader.t5_session is mock_sessions
        assert loader.t5_tokenizer is mock_tokenizer

    @pytest.mark.asyncio
    async def test_load_t5_failure_graceful(self) -> None:
        """load_t5 logs warning on failure, does not raise."""
        config = ServerConfig(disable_t5=False, disable_slop=True, disable_embed=True)
        loader = ModelLoader(config)
        with patch(
            "phraseturner.models.loader.asyncio.to_thread",
            side_effect=FileNotFoundError("model not found"),
        ):
            await loader.load_t5()
        assert not loader.t5_available


# ---------------------------------------------------------------------------
# models/loader.py — warmup_t5 success path (lines 325-344)
# ---------------------------------------------------------------------------
class TestLoaderWarmupSuccess:
    """Tests for ModelLoader.warmup_t5() success path."""

    @pytest.mark.asyncio
    async def test_warmup_t5_success(self) -> None:
        """warmup_t5 completes without error when T5 is available."""
        config = ServerConfig(disable_t5=True, disable_slop=True, disable_embed=True)
        loader = ModelLoader(config)
        loader._t5_session = (MagicMock(), MagicMock())
        loader._t5_tokenizer = MagicMock()
        with patch(
            "phraseturner.models.loader.asyncio.to_thread",
            return_value=None,
        ):
            await loader.warmup_t5()
        # No exception means success


# ---------------------------------------------------------------------------
# server.py — app_lifespan (lines 46-48, 71-127)
# ---------------------------------------------------------------------------
class TestAppLifespan:
    """Tests for the app_lifespan context manager."""

    @pytest.mark.asyncio
    async def test_lifespan_yields_context_dict(self) -> None:
        """app_lifespan yields dict with config, persona_index, models."""
        from phraseturner.server import app_lifespan

        mock_server = MagicMock()
        mock_models = MagicMock(spec=ModelLoader)
        mock_models.fastembed_available = False
        mock_models.t5_available = False
        mock_models.operating_tier = 0
        mock_models.model_versions = {}
        mock_models.load_spacy = AsyncMock()
        mock_models.load_fastembed = AsyncMock()
        mock_models.load_slop_detector = AsyncMock()
        mock_models.load_t5 = AsyncMock()
        mock_models.cleanup = AsyncMock()

        mock_persona_index = MagicMock()
        mock_persona_index.load_all = AsyncMock()
        mock_persona_index.count = 0
        mock_persona_index.watch_for_changes = AsyncMock(
            return_value=None
        )

        with (
            patch("phraseturner.server.get_config") as mock_get_config,
            patch("phraseturner.server.ModelLoader", return_value=mock_models),
            patch("phraseturner.server.PersonaIndex", return_value=mock_persona_index),
        ):
            mock_get_config.return_value = ServerConfig(
                disable_t5=True, disable_slop=True, disable_embed=True
            )
            async with app_lifespan(mock_server) as ctx:
                assert "config" in ctx
                assert "persona_index" in ctx
                assert "models" in ctx
                assert ctx["models"] is mock_models
                assert ctx["persona_index"] is mock_persona_index

        mock_models.cleanup.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lifespan_spacy_failure_degrades(self) -> None:
        """app_lifespan continues when spaCy fails to load (Tier 0)."""
        from phraseturner.server import app_lifespan

        mock_server = MagicMock()
        mock_models = MagicMock(spec=ModelLoader)
        mock_models.fastembed_available = False
        mock_models.t5_available = False
        mock_models.operating_tier = 0
        mock_models.model_versions = {}
        mock_models.load_spacy = AsyncMock(side_effect=OSError("spacy failed"))
        mock_models.load_fastembed = AsyncMock()
        mock_models.load_slop_detector = AsyncMock()
        mock_models.load_t5 = AsyncMock()
        mock_models.cleanup = AsyncMock()

        mock_persona_index = MagicMock()
        mock_persona_index.load_all = AsyncMock()
        mock_persona_index.count = 0
        mock_persona_index.watch_for_changes = AsyncMock(
            return_value=None
        )

        with (
            patch("phraseturner.server.get_config") as mock_get_config,
            patch("phraseturner.server.ModelLoader", return_value=mock_models),
            patch("phraseturner.server.PersonaIndex", return_value=mock_persona_index),
        ):
            mock_get_config.return_value = ServerConfig(
                disable_t5=True, disable_slop=True, disable_embed=True
            )
            async with app_lifespan(mock_server) as ctx:
                assert ctx["models"] is mock_models

    @pytest.mark.asyncio
    async def test_lifespan_builds_embeddings_when_fastembed_available(self) -> None:
        """app_lifespan builds persona embeddings when FastEmbed is loaded."""
        from phraseturner.server import app_lifespan

        mock_server = MagicMock()
        mock_models = MagicMock(spec=ModelLoader)
        mock_models.fastembed_available = True
        mock_models.fastembed = MagicMock()
        mock_models.t5_available = True
        mock_models.operating_tier = 4
        mock_models.model_versions = {"fastembed": "bge-small-en-v1.5"}
        mock_models.load_spacy = AsyncMock()
        mock_models.load_fastembed = AsyncMock()
        mock_models.load_slop_detector = AsyncMock()
        mock_models.load_t5 = AsyncMock()
        mock_models.warmup_t5 = AsyncMock()
        mock_models.cleanup = AsyncMock()

        mock_persona_index = MagicMock()
        mock_persona_index.load_all = AsyncMock()
        mock_persona_index.build_embeddings = AsyncMock()
        mock_persona_index.count = 5
        mock_persona_index.watch_for_changes = AsyncMock(
            return_value=None
        )

        with (
            patch("phraseturner.server.get_config") as mock_get_config,
            patch("phraseturner.server.ModelLoader", return_value=mock_models),
            patch("phraseturner.server.PersonaIndex", return_value=mock_persona_index),
        ):
            mock_get_config.return_value = ServerConfig(
                disable_t5=True, disable_slop=True, disable_embed=True
            )
            async with app_lifespan(mock_server):
                pass

        mock_persona_index.build_embeddings.assert_awaited_once_with(
            mock_models.fastembed
        )
        mock_models.warmup_t5.assert_awaited_once()


# ---------------------------------------------------------------------------
# t5/context.py — T5Runner inference methods (lines 445-604)
# ---------------------------------------------------------------------------
class TestT5RunnerInference:
    """Tests for T5Runner._infer, _greedy_decode, _beam_search_decode."""

    def _make_runner(self) -> Any:
        """Create a T5Runner with mock encoder/decoder sessions."""
        from phraseturner.t5.context import T5Runner

        encoder = MagicMock()
        decoder = MagicMock()
        tokenizer = MagicMock()

        # Configure tokenizer
        tokenizer.pad_token_id = 0
        tokenizer.eos_token_id = 1
        tokenizer.return_value = {
            "input_ids": np.array([[10, 20, 30, 0, 0]], dtype=np.int64),
            "attention_mask": np.array([[1, 1, 1, 0, 0]], dtype=np.int64),
        }
        tokenizer.decode.return_value = "formal"

        # Configure encoder — returns hidden states
        encoder.run.return_value = [
            np.random.randn(1, 5, 64).astype(np.float32)
        ]

        # Configure decoder — returns logits with clear argmax
        vocab_size = 100
        logits = np.zeros((1, 1, vocab_size), dtype=np.float32)
        logits[0, 0, 42] = 10.0  # Token 42 has highest logit
        # Second call returns EOS
        logits_eos = np.zeros((1, 1, vocab_size), dtype=np.float32)
        logits_eos[0, 0, 1] = 10.0  # EOS token
        decoder.run.side_effect = [
            [logits.copy()],
            [logits_eos.copy()],
        ]

        return T5Runner(session=(encoder, decoder), tokenizer=tokenizer)

    def test_greedy_decode(self) -> None:
        """_greedy_decode returns decoded text with confidence 1.0."""
        runner = self._make_runner()
        text, confidence = runner._greedy_decode(
            encoder_hidden=np.random.randn(1, 5, 64).astype(np.float32),
            attention_mask=np.array([[1, 1, 1, 0, 0]], dtype=np.int64),
            max_tokens=10,
        )
        assert isinstance(text, str)
        assert confidence == 1.0

    def test_beam_search_decode(self) -> None:
        """_beam_search_decode returns decoded text with confidence in [0, 1]."""
        from phraseturner.t5.context import T5Runner

        encoder = MagicMock()
        decoder = MagicMock()
        tokenizer = MagicMock()
        tokenizer.pad_token_id = 0
        tokenizer.eos_token_id = 1
        tokenizer.decode.return_value = "formal"

        # Decoder returns logits that lead to EOS quickly
        vocab_size = 100
        logits = np.zeros((1, 1, vocab_size), dtype=np.float32)
        logits[0, 0, 1] = 10.0  # EOS token has highest probability
        decoder.run.return_value = [logits]

        runner = T5Runner(session=(encoder, decoder), tokenizer=tokenizer)
        text, confidence = runner._beam_search_decode(
            encoder_hidden=np.random.randn(1, 5, 64).astype(np.float32),
            attention_mask=np.array([[1, 1, 1, 0, 0]], dtype=np.int64),
            max_tokens=5,
            num_beams=2,
        )
        assert isinstance(text, str)
        assert 0.0 <= confidence <= 1.0

    def test_infer_greedy(self) -> None:
        """_infer with use_beam=False calls greedy decode."""
        runner = self._make_runner()
        text, confidence = runner._infer("classify: hello", max_tokens=8, use_beam=False)
        assert isinstance(text, str)
        assert confidence == 1.0

    def test_infer_beam(self) -> None:
        """_infer with use_beam=True calls beam search decode."""
        from phraseturner.t5.context import T5Runner

        encoder = MagicMock()
        decoder = MagicMock()
        tokenizer = MagicMock()
        tokenizer.pad_token_id = 0
        tokenizer.eos_token_id = 1
        tokenizer.return_value = {
            "input_ids": np.array([[10, 20, 0, 0, 0]], dtype=np.int64),
            "attention_mask": np.array([[1, 1, 0, 0, 0]], dtype=np.int64),
        }
        tokenizer.decode.return_value = "informal"

        vocab_size = 100
        logits = np.zeros((1, 1, vocab_size), dtype=np.float32)
        logits[0, 0, 1] = 10.0  # EOS
        decoder.run.return_value = [logits]

        encoder.run.return_value = [
            np.random.randn(1, 5, 64).astype(np.float32)
        ]

        runner = T5Runner(session=(encoder, decoder), tokenizer=tokenizer)
        text, confidence = runner._infer("classify: hello", max_tokens=8, use_beam=True)
        assert isinstance(text, str)
        assert 0.0 <= confidence <= 1.0

    @pytest.mark.asyncio
    async def test_run_task_delegates_to_infer(self) -> None:
        """run_task calls _infer via to_thread."""
        runner = self._make_runner()
        text, confidence = await runner.run_task(
            prompt="classify: hello",
            max_tokens=8,
            use_beam=False,
        )
        assert isinstance(text, str)
        assert confidence == 1.0

    def test_beam_search_empty_sequences(self) -> None:
        """_beam_search_decode handles case where no candidates remain."""
        from phraseturner.t5.context import T5Runner

        encoder = MagicMock()
        decoder = MagicMock()
        tokenizer = MagicMock()
        tokenizer.pad_token_id = 0
        tokenizer.eos_token_id = 1
        tokenizer.decode.return_value = ""

        # All beams immediately produce EOS
        vocab_size = 50
        logits = np.zeros((1, 1, vocab_size), dtype=np.float32)
        logits[0, 0, 1] = 100.0  # EOS overwhelmingly
        decoder.run.return_value = [logits]

        runner = T5Runner(session=(encoder, decoder), tokenizer=tokenizer)
        text, confidence = runner._beam_search_decode(
            encoder_hidden=np.random.randn(1, 5, 64).astype(np.float32),
            attention_mask=np.array([[1, 1, 0, 0, 0]], dtype=np.int64),
            max_tokens=5,
            num_beams=4,
        )
        assert isinstance(text, str)
        assert 0.0 <= confidence <= 1.0

    def test_beam_search_multi_token_output(self) -> None:
        """_beam_search_decode produces multi-token output before EOS."""
        from phraseturner.t5.context import T5Runner

        encoder = MagicMock()
        decoder = MagicMock()
        tokenizer = MagicMock()
        tokenizer.pad_token_id = 0
        tokenizer.eos_token_id = 1
        tokenizer.decode.return_value = "formal style"

        vocab_size = 100
        # First call: token 42 is best
        logits1 = np.zeros((1, 1, vocab_size), dtype=np.float32)
        logits1[0, 0, 42] = 10.0
        logits1[0, 0, 43] = 8.0
        # Second call: EOS is best
        logits2 = np.zeros((1, 1, vocab_size), dtype=np.float32)
        logits2[0, 0, 1] = 10.0

        call_count = [0]
        def mock_run(_, inputs):
            call_count[0] += 1
            if call_count[0] <= 4:  # First round (up to num_beams calls)
                return [logits1.copy()]
            return [logits2.copy()]

        decoder.run.side_effect = mock_run

        runner = T5Runner(session=(encoder, decoder), tokenizer=tokenizer)
        text, confidence = runner._beam_search_decode(
            encoder_hidden=np.random.randn(1, 5, 64).astype(np.float32),
            attention_mask=np.array([[1, 1, 0, 0, 0]], dtype=np.int64),
            max_tokens=5,
            num_beams=2,
        )
        assert isinstance(text, str)
        assert 0.0 <= confidence <= 1.0


# ---------------------------------------------------------------------------
# personas/rules.py — metric rule type (lines 626-667)
# ---------------------------------------------------------------------------
class TestMetricRuleEvaluation:
    """Tests for the metric rule type in RuleEvaluator."""

    def test_metric_rule_flesch_reading_ease_violation(self) -> None:
        """Metric rule detects when flesch_reading_ease is below min threshold."""
        from phraseturner.personas.rules import RuleEvaluator
        from phraseturner.personas.schema import RuleConfig, RuleType

        evaluator = RuleEvaluator()
        rule = RuleConfig(
            id="metric-readability",
            type=RuleType.METRIC,
            level="warning",
            metric="flesch_reading_ease",
            min=80.0,  # Require high readability
        )
        # Complex text should have low Flesch Reading Ease
        text = (
            "The implementation of the aforementioned methodological "
            "framework necessitates a comprehensive understanding of "
            "the multifaceted epistemological considerations inherent "
            "in the paradigmatic analysis of sociolinguistic phenomena."
        )
        matches = evaluator.evaluate(rule, text, [text])
        assert len(matches) >= 1
        assert matches[0].rule_id == "metric-readability"

    def test_metric_rule_no_violation(self) -> None:
        """Metric rule passes when value is within thresholds."""
        from phraseturner.personas.rules import RuleEvaluator
        from phraseturner.personas.schema import RuleConfig, RuleType

        evaluator = RuleEvaluator()
        rule = RuleConfig(
            id="metric-easy",
            type=RuleType.METRIC,
            level="warning",
            metric="flesch_reading_ease",
            min=0.0,
            max=120.0,
        )
        text = "The cat sat on the mat. It was a nice day."
        matches = evaluator.evaluate(rule, text, [text])
        assert len(matches) == 0

    def test_metric_rule_unknown_metric(self) -> None:
        """Metric rule returns empty for unknown metric name."""
        from phraseturner.personas.rules import RuleEvaluator
        from phraseturner.personas.schema import RuleConfig, RuleType

        evaluator = RuleEvaluator()
        rule = RuleConfig(
            id="metric-unknown",
            type=RuleType.METRIC,
            level="warning",
            metric="nonexistent_metric",
        )
        matches = evaluator.evaluate(rule, "Some text.", ["Some text."])
        assert len(matches) == 0

    def test_metric_rule_no_metric_field(self) -> None:
        """Metric rule returns empty when metric field is None."""
        from phraseturner.personas.rules import RuleEvaluator
        from phraseturner.personas.schema import RuleConfig, RuleType

        evaluator = RuleEvaluator()
        rule = RuleConfig(
            id="metric-none",
            type=RuleType.METRIC,
            level="warning",
            metric=None,
        )
        matches = evaluator.evaluate(rule, "Some text.", ["Some text."])
        assert len(matches) == 0

    def test_metric_rule_max_violation(self) -> None:
        """Metric rule detects when value exceeds max threshold."""
        from phraseturner.personas.rules import RuleEvaluator
        from phraseturner.personas.schema import RuleConfig, RuleType

        evaluator = RuleEvaluator()
        rule = RuleConfig(
            id="metric-max",
            type=RuleType.METRIC,
            level="error",
            metric="flesch_kincaid_grade",
            max=5.0,  # Require very simple text
        )
        text = (
            "The implementation of the aforementioned methodological "
            "framework necessitates a comprehensive understanding."
        )
        matches = evaluator.evaluate(rule, text, [text])
        assert len(matches) >= 1
