"""Tests for PersonaIndex semantic search (§3.5, FR-PERSONA-05).

Validates: FR-PERSONA-05 (AC-FR-PERSONA-05.1, AC-FR-PERSONA-05.2, AC-FR-PERSONA-05.3).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest
import yaml

from phraseturner.config import ServerConfig
from phraseturner.personas.index import PersonaIndex

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PERSONA_A = {
    "name": "slack-casual",
    "version": "1.0.0",
    "description": "Casual tone for Slack messages and team chat.",
}

_PERSONA_B = {
    "name": "technical-docs",
    "version": "1.0.0",
    "description": "Formal technical documentation style.",
}

_PERSONA_C = {
    "name": "email-professional",
    "version": "1.0.0",
    "description": "Professional email communication.",
}


def _write_persona(directory: Path, data: dict[str, object]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{data['name']}.yaml"
    path.write_text(yaml.dump(data), encoding="utf-8")
    return path


class FakeFastEmbed:
    """Fake FastEmbed model that returns deterministic embeddings.

    Maps known text prefixes to fixed vectors for predictable cosine
    similarity results.
    """

    def __init__(self, dim: int = 4) -> None:
        self._dim = dim
        # Pre-defined embeddings for known texts
        self._known: dict[str, list[float]] = {
            "slack": [1.0, 0.0, 0.0, 0.0],
            "casual": [0.9, 0.1, 0.0, 0.0],
            "technical": [0.0, 1.0, 0.0, 0.0],
            "docs": [0.0, 0.9, 0.1, 0.0],
            "email": [0.0, 0.0, 1.0, 0.0],
            "professional": [0.0, 0.0, 0.9, 0.1],
        }

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return embeddings for the given texts.

        Uses keyword matching to return pre-defined vectors. Falls back
        to a random-ish vector based on text hash for unknown texts.
        """
        results: list[list[float]] = []
        for text in texts:
            text_lower = text.lower()
            matched = False
            for keyword, vec in self._known.items():
                if keyword in text_lower:
                    results.append(vec)
                    matched = True
                    break
            if not matched:
                # Deterministic fallback based on text length
                seed = len(text) % self._dim
                vec = [0.0] * self._dim
                vec[seed] = 0.5
                results.append(vec)
        return results


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def user_dir(tmp_path: Path) -> Path:
    d = tmp_path / "user-personas"
    d.mkdir()
    return d


@pytest.fixture()
def config(user_dir: Path) -> ServerConfig:
    return ServerConfig(personas_dir=user_dir)


@pytest.fixture()
def fake_fastembed() -> FakeFastEmbed:
    return FakeFastEmbed()


# ---------------------------------------------------------------------------
# embeddings_available property
# ---------------------------------------------------------------------------


class TestEmbeddingsAvailable:
    """Tests for PersonaIndex.embeddings_available property."""

    def test_false_initially(self, config: ServerConfig) -> None:
        """Embeddings are not available before build_embeddings is called."""
        index = PersonaIndex(config)
        assert index.embeddings_available is False

    @pytest.mark.asyncio()
    async def test_true_after_build(
        self,
        config: ServerConfig,
        user_dir: Path,
        fake_fastembed: FakeFastEmbed,
    ) -> None:
        """Embeddings are available after build_embeddings succeeds."""
        _write_persona(user_dir, _PERSONA_A)
        index = PersonaIndex(config)
        await index.load_all()
        await index.build_embeddings(fake_fastembed)
        assert index.embeddings_available is True

    @pytest.mark.asyncio()
    async def test_embeddings_built_with_builtin_personas(
        self,
        config: ServerConfig,
        fake_fastembed: FakeFastEmbed,
    ) -> None:
        """Embeddings are available when built-in personas are loaded."""
        index = PersonaIndex(config)
        await index.load_all()
        await index.build_embeddings(fake_fastembed)
        # Built-in personas are always loaded, so embeddings are available
        assert index.embeddings_available is True


# ---------------------------------------------------------------------------
# build_embeddings
# ---------------------------------------------------------------------------


class TestBuildEmbeddings:
    """Tests for PersonaIndex.build_embeddings()."""

    @pytest.mark.asyncio()
    async def test_builds_for_all_personas(
        self,
        config: ServerConfig,
        user_dir: Path,
        fake_fastembed: FakeFastEmbed,
    ) -> None:
        """AC-FR-PERSONA-05.1: all persona descriptions are embedded."""
        _write_persona(user_dir, _PERSONA_A)
        _write_persona(user_dir, _PERSONA_B)
        _write_persona(user_dir, _PERSONA_C)

        index = PersonaIndex(config)
        await index.load_all()
        await index.build_embeddings(fake_fastembed)

        # All 3 personas should have embeddings (plus any built-ins)
        assert "slack-casual" in index._embeddings
        assert "technical-docs" in index._embeddings
        assert "email-professional" in index._embeddings

    @pytest.mark.asyncio()
    async def test_stores_numpy_arrays(
        self,
        config: ServerConfig,
        user_dir: Path,
        fake_fastembed: FakeFastEmbed,
    ) -> None:
        """Embeddings are stored as numpy float32 arrays."""
        _write_persona(user_dir, _PERSONA_A)
        index = PersonaIndex(config)
        await index.load_all()
        await index.build_embeddings(fake_fastembed)

        emb = index._embeddings["slack-casual"]
        assert isinstance(emb, np.ndarray)
        assert emb.dtype == np.float32

    @pytest.mark.asyncio()
    async def test_stores_fastembed_model_ref(
        self,
        config: ServerConfig,
        user_dir: Path,
        fake_fastembed: FakeFastEmbed,
    ) -> None:
        """The fastembed model reference is stored for query embedding."""
        _write_persona(user_dir, _PERSONA_A)
        index = PersonaIndex(config)
        await index.load_all()
        await index.build_embeddings(fake_fastembed)
        assert index._fastembed_model is fake_fastembed

    @pytest.mark.asyncio()
    async def test_rebuild_clears_previous(
        self,
        config: ServerConfig,
        user_dir: Path,
        fake_fastembed: FakeFastEmbed,
    ) -> None:
        """Calling build_embeddings again replaces previous embeddings."""
        _write_persona(user_dir, _PERSONA_A)
        index = PersonaIndex(config)
        await index.load_all()
        await index.build_embeddings(fake_fastembed)
        assert index.embeddings_available is True

        # Clear personas and rebuild — should have no embeddings
        index._personas.clear()
        await index.build_embeddings(fake_fastembed)
        assert index.embeddings_available is False


# ---------------------------------------------------------------------------
# search — semantic path
# ---------------------------------------------------------------------------


class TestSearchSemantic:
    """Tests for semantic search when embeddings are available."""

    @pytest.mark.asyncio()
    async def test_returns_ranked_results(
        self,
        config: ServerConfig,
        user_dir: Path,
        fake_fastembed: FakeFastEmbed,
    ) -> None:
        """AC-FR-PERSONA-05.2: results ranked by cosine similarity."""
        _write_persona(user_dir, _PERSONA_A)
        _write_persona(user_dir, _PERSONA_B)
        _write_persona(user_dir, _PERSONA_C)

        index = PersonaIndex(config)
        await index.load_all()
        await index.build_embeddings(fake_fastembed)

        results = index.search("slack chat")
        assert len(results) > 0
        # Results should be sorted by descending similarity
        scores = [score for _, score in results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio()
    async def test_respects_limit(
        self,
        config: ServerConfig,
        user_dir: Path,
        fake_fastembed: FakeFastEmbed,
    ) -> None:
        """Search respects the limit parameter."""
        _write_persona(user_dir, _PERSONA_A)
        _write_persona(user_dir, _PERSONA_B)
        _write_persona(user_dir, _PERSONA_C)

        index = PersonaIndex(config)
        await index.load_all()
        await index.build_embeddings(fake_fastembed)

        results = index.search("anything", limit=1)
        assert len(results) <= 1

    @pytest.mark.asyncio()
    async def test_returns_tuples_of_name_and_score(
        self,
        config: ServerConfig,
        user_dir: Path,
        fake_fastembed: FakeFastEmbed,
    ) -> None:
        """Each result is a (name, score) tuple."""
        _write_persona(user_dir, _PERSONA_A)
        index = PersonaIndex(config)
        await index.load_all()
        await index.build_embeddings(fake_fastembed)

        results = index.search("casual")
        assert len(results) > 0
        name, score = results[0]
        assert isinstance(name, str)
        assert isinstance(score, float)


# ---------------------------------------------------------------------------
# search — substring fallback
# ---------------------------------------------------------------------------


class TestSearchSubstring:
    """Tests for substring fallback when FastEmbed is unavailable."""

    @pytest.mark.asyncio()
    async def test_exact_name_match_scores_1(
        self,
        config: ServerConfig,
        user_dir: Path,
    ) -> None:
        """AC-FR-PERSONA-05.3: exact name match returns score 1.0."""
        _write_persona(user_dir, _PERSONA_A)
        index = PersonaIndex(config)
        await index.load_all()

        # No embeddings built — should use substring fallback
        results = index.search("slack-casual")
        assert len(results) >= 1
        name, score = results[0]
        assert name == "slack-casual"
        assert score == 1.0

    @pytest.mark.asyncio()
    async def test_substring_match_scores_half(
        self,
        config: ServerConfig,
        user_dir: Path,
    ) -> None:
        """AC-FR-PERSONA-05.3: substring match returns score 0.5."""
        _write_persona(user_dir, _PERSONA_A)
        index = PersonaIndex(config)
        await index.load_all()

        results = index.search("slack")
        assert len(results) >= 1
        name, score = results[0]
        assert name == "slack-casual"
        assert score == 0.5

    @pytest.mark.asyncio()
    async def test_description_substring_match(
        self,
        config: ServerConfig,
        user_dir: Path,
    ) -> None:
        """Substring matching also searches persona descriptions."""
        _write_persona(user_dir, _PERSONA_B)
        index = PersonaIndex(config)
        await index.load_all()

        results = index.search("documentation")
        assert len(results) >= 1
        assert results[0][0] == "technical-docs"
        assert results[0][1] == 0.5

    @pytest.mark.asyncio()
    async def test_case_insensitive(
        self,
        config: ServerConfig,
        user_dir: Path,
    ) -> None:
        """Substring matching is case-insensitive."""
        _write_persona(user_dir, _PERSONA_A)
        index = PersonaIndex(config)
        await index.load_all()

        results = index.search("SLACK-CASUAL")
        assert len(results) >= 1
        assert results[0][0] == "slack-casual"
        assert results[0][1] == 1.0

    @pytest.mark.asyncio()
    async def test_no_match_returns_empty(
        self,
        config: ServerConfig,
        user_dir: Path,
    ) -> None:
        """No match returns an empty list."""
        _write_persona(user_dir, _PERSONA_A)
        index = PersonaIndex(config)
        await index.load_all()

        results = index.search("zzz-nonexistent-zzz")
        assert results == []

    @pytest.mark.asyncio()
    async def test_respects_limit(
        self,
        config: ServerConfig,
        user_dir: Path,
    ) -> None:
        """Substring search respects the limit parameter."""
        _write_persona(user_dir, _PERSONA_A)
        _write_persona(user_dir, _PERSONA_B)
        _write_persona(user_dir, _PERSONA_C)
        index = PersonaIndex(config)
        await index.load_all()

        # All three have descriptions — "a" should match something
        results = index.search("a", limit=1)
        assert len(results) <= 1


# ---------------------------------------------------------------------------
# _cosine_similarity
# ---------------------------------------------------------------------------


class TestCosineSimilarity:
    """Tests for PersonaIndex._cosine_similarity()."""

    def test_identical_vectors(self) -> None:
        """Identical vectors have similarity 1.0."""
        v = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        assert PersonaIndex._cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self) -> None:
        """Orthogonal vectors have similarity 0.0."""
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([0.0, 1.0], dtype=np.float32)
        assert PersonaIndex._cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self) -> None:
        """Opposite vectors have similarity -1.0."""
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([-1.0, 0.0], dtype=np.float32)
        assert PersonaIndex._cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector_returns_zero(self) -> None:
        """Zero vector returns 0.0 (no division by zero)."""
        a = np.array([0.0, 0.0], dtype=np.float32)
        b = np.array([1.0, 2.0], dtype=np.float32)
        assert PersonaIndex._cosine_similarity(a, b) == 0.0

    def test_both_zero_vectors(self) -> None:
        """Both zero vectors return 0.0."""
        z = np.array([0.0, 0.0], dtype=np.float32)
        assert PersonaIndex._cosine_similarity(z, z) == 0.0

    def test_similar_vectors_high_score(self) -> None:
        """Similar vectors produce a high similarity score."""
        a = np.array([1.0, 0.9, 0.0], dtype=np.float32)
        b = np.array([0.9, 1.0, 0.0], dtype=np.float32)
        sim = PersonaIndex._cosine_similarity(a, b)
        assert sim > 0.9

    def test_returns_float(self) -> None:
        """Result is a Python float, not numpy scalar."""
        a = np.array([1.0, 2.0], dtype=np.float32)
        b = np.array([3.0, 4.0], dtype=np.float32)
        result = PersonaIndex._cosine_similarity(a, b)
        assert isinstance(result, float)
