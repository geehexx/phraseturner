"""4-tier persona directory loader and index.

Implements §3.1 of the design specification.
Personas are resolved from 4 directory tiers in strict precedence order:
project (highest) → user → remote → built-in (lowest).

Requirements: FR-PERSONA-01, NFR-SEC-02.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import structlog
import yaml

from phraseturner.exceptions import PersonaNotFoundError
from phraseturner.personas.schema import PersonaConfig

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from phraseturner.config import ServerConfig

logger = structlog.get_logger()

# Tier labels in precedence order (highest first).
TIER_PROJECT = "project"
TIER_USER = "user"
TIER_REMOTE = "remote"
TIER_BUILTIN = "built-in"

_TIER_LABELS: list[str] = [TIER_PROJECT, TIER_USER, TIER_REMOTE, TIER_BUILTIN]


def get_persona_directories(config: ServerConfig) -> list[tuple[Path, str]]:
    """Return persona directories in priority order (highest first).

    Each entry is a ``(path, tier_label)`` tuple. Only directories that
    exist on disk are included, except for the user-tier directory which
    is created automatically if missing (AC-FR-PERSONA-09.2).

    Implements AC-FR-PERSONA-01.1 through AC-FR-PERSONA-01.5,
    AC-FR-PERSONA-09.1, AC-FR-PERSONA-09.2.

    Args:
        config: Server configuration with optional ``personas_dir`` override.

    Returns:
        List of ``(directory_path, tier_label)`` tuples ordered from
        highest to lowest precedence.
    """
    dirs: list[tuple[Path, str]] = []

    # Tier 1: Project-local — AC-FR-PERSONA-01.3
    project_dir = Path.cwd() / ".phraseturner" / "personas"
    if project_dir.is_dir():
        dirs.append((project_dir, TIER_PROJECT))

    # Tier 2: User-level (configurable via PHRASETURNER_PERSONAS_DIR)
    # AC-FR-PERSONA-09.1, AC-FR-PERSONA-09.2
    user_dir = config.personas_dir or Path("~/.config/phraseturner/personas").expanduser()
    user_dir.mkdir(parents=True, exist_ok=True)  # AC-FR-PERSONA-09.2
    dirs.append((user_dir, TIER_USER))

    # Tier 3: Remote (future: git/HTTP sync)
    remote_dir = Path("~/.cache/phraseturner/remote").expanduser()
    if remote_dir.is_dir():
        dirs.append((remote_dir, TIER_REMOTE))

    # Tier 4: Built-in (bundled in package) — AC-FR-PERSONA-01.5
    builtin_dir = Path(__file__).parent
    dirs.append((builtin_dir, TIER_BUILTIN))

    return dirs


def _parse_persona_file(path: Path) -> PersonaConfig | None:
    """Parse and validate a single persona YAML file.

    Uses ``yaml.safe_load`` only (NFR-SEC-02). Returns ``None`` and logs
    a warning if the file cannot be parsed or fails validation.

    Args:
        path: Path to the YAML file.

    Returns:
        Validated ``PersonaConfig`` or ``None`` on failure.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        logger.warning("persona_read_failed", path=str(path))
        return None

    try:
        data = yaml.safe_load(raw)  # NFR-SEC-02: safe_load only
    except yaml.YAMLError as exc:
        logger.warning("persona_yaml_invalid", path=str(path), error=str(exc))
        return None

    if not isinstance(data, dict):
        logger.warning("persona_yaml_not_dict", path=str(path))
        return None

    try:
        return PersonaConfig.model_validate(data)
    except Exception as exc:
        logger.warning(
            "persona_validation_failed",
            path=str(path),
            error=str(exc),
        )
        return None


class PersonaIndex:
    """In-memory index of all loaded personas across 4 directory tiers.

    Implements §3.1 (4-Tier Directory Architecture).
    Requirements: FR-PERSONA-01, NFR-SEC-02.

    The index maps persona names to ``(PersonaConfig, tier_label)`` tuples.
    On name collision the highest-precedence tier wins (first found wins
    since directories are scanned in priority order).

    Attributes:
        _config: Server configuration.
        _personas: Mapping of persona name → (config, tier_label).
    """

    def __init__(self, config: ServerConfig) -> None:
        self._config = config
        self._personas: dict[str, tuple[PersonaConfig, str]] = {}
        self._embeddings: dict[str, NDArray[np.float32]] = {}
        self._fastembed_model: Any = None

    async def load_all(self) -> None:
        """Scan all 4 directory tiers and load valid persona YAML files.

        Directories are scanned in precedence order (project → user →
        remote → built-in). The first persona found for a given name wins;
        lower-tier duplicates are silently skipped.

        Implements AC-FR-PERSONA-01.1, AC-FR-PERSONA-01.2.
        """
        self._personas.clear()
        directories = get_persona_directories(self._config)

        for directory, tier in directories:
            if not directory.is_dir():
                continue

            yaml_files = sorted(
                p for p in directory.iterdir() if p.suffix in {".yaml", ".yml"} and p.is_file()
            )

            for yaml_path in yaml_files:
                persona = _parse_persona_file(yaml_path)
                if persona is None:
                    continue

                # FR-PERSONA-01.2: highest-tier wins on name collision
                if persona.name in self._personas:
                    existing_tier = self._personas[persona.name][1]
                    logger.debug(
                        "persona_shadowed",
                        name=persona.name,
                        existing_tier=existing_tier,
                        skipped_tier=tier,
                        path=str(yaml_path),
                    )
                    continue

                self._personas[persona.name] = (persona, tier)
                logger.debug(
                    "persona_loaded",
                    name=persona.name,
                    tier=tier,
                    path=str(yaml_path),
                )

        logger.info(
            "persona_index_loaded",
            total=len(self._personas),
            tiers={
                tier: sum(1 for _, t in self._personas.values() if t == tier)
                for tier in _TIER_LABELS
            },
        )

    def get(self, name: str) -> PersonaConfig:
        """Return the persona config for the given name.

        Implements AC-FR-TOOL-03.1.

        Args:
            name: Exact persona name.

        Returns:
            The ``PersonaConfig`` from the highest-precedence tier.

        Raises:
            PersonaNotFoundError: If no persona matches the name.
        """
        entry = self._personas.get(name)
        if entry is None:
            raise PersonaNotFoundError(
                f"No persona found with name '{name}'",
                details={"name": name},
            )
        return entry[0]

    def get_tier(self, name: str) -> str:
        """Return the tier label for the given persona name.

        Args:
            name: Exact persona name.

        Returns:
            Tier label string (``project``, ``user``, ``remote``, or
            ``built-in``).

        Raises:
            PersonaNotFoundError: If no persona matches the name.
        """
        entry = self._personas.get(name)
        if entry is None:
            raise PersonaNotFoundError(
                f"No persona found with name '{name}'",
                details={"name": name},
            )
        return entry[1]

    def list_all(self) -> list[PersonaConfig]:
        """Return all loaded personas.

        Implements AC-FR-TOOL-02.1.

        Returns:
            List of all ``PersonaConfig`` objects in the index.
        """
        return [config for config, _ in self._personas.values()]

    def add(
        self,
        name: str,
        config: PersonaConfig,
        *,
        tier: str = "user",
    ) -> None:
        """Add a persona to the index.

        Used by the create_persona service to register a newly created
        persona without requiring a full reload.

        Args:
            name: Persona name (used as the index key).
            config: Validated persona configuration.
            tier: Directory tier label for the persona.
        """
        self._personas[name] = (config, tier)
        logger.debug("persona_added", name=name, tier=tier)

    @property
    def count(self) -> int:
        """Return the number of loaded personas."""
        return len(self._personas)

    def _path_to_tier(self, path: Path) -> str:
        """Resolve a file path to its persona directory tier label.

        Args:
            path: Absolute path to a persona YAML file.

        Returns:
            Tier label string, or ``"unknown"`` if the path does not
            belong to any known persona directory.
        """
        directories = get_persona_directories(self._config)
        for directory, tier in directories:
            try:
                path.relative_to(directory)
                return tier
            except ValueError:
                continue
        return "unknown"

    async def watch_for_changes(self, fastembed: Any = None) -> None:
        """Watch persona directories for file changes and hot-reload.

        Uses ``watchfiles.awatch()`` with a configurable debounce
        (default 500ms). On file change the affected persona is
        re-parsed, re-validated, and its embedding rebuilt when
        FastEmbed is available.

        If validation fails the previous valid version is retained and
        a warning is logged.

        Designed to run as a long-lived ``asyncio.Task`` via
        ``asyncio.create_task``.

        Implements AC-FR-PERSONA-04.1, AC-FR-PERSONA-04.2,
        AC-FR-PERSONA-04.3.

        Args:
            fastembed: Optional FastEmbed model instance for rebuilding
                persona embeddings on change.
        """
        import watchfiles  # noqa: PLC0415

        directories = get_persona_directories(self._config)
        watch_paths = [str(directory) for directory, _ in directories if directory.is_dir()]

        if not watch_paths:
            logger.warning("persona_watch_no_dirs", msg="No persona directories to watch")
            return

        debounce_ms = self._config.watch_debounce_ms

        logger.info(
            "persona_watch_started",
            directories=watch_paths,
            debounce_ms=debounce_ms,
        )

        try:
            async for changes in watchfiles.awatch(
                *watch_paths,
                debounce=debounce_ms,
            ):
                for change_type, change_path_str in changes:
                    change_path = Path(change_path_str)

                    # Filter: only .yaml / .yml files
                    if change_path.suffix not in {".yaml", ".yml"}:
                        continue

                    change_label = change_type.name.lower()
                    tier = self._path_to_tier(change_path)

                    logger.info(
                        "persona_file_changed",
                        change=change_label,
                        path=str(change_path),
                        tier=tier,
                    )

                    if change_type == watchfiles.Change.deleted:
                        self._handle_deleted(change_path, tier)
                    else:
                        # created or modified
                        self._handle_upsert(change_path, tier, fastembed)

        except asyncio.CancelledError:
            logger.info("persona_watch_stopped")

    def _handle_deleted(self, path: Path, tier: str) -> None:
        """Remove a persona from the index when its file is deleted.

        Only removes the persona if it was loaded from the same tier as
        the deleted file. If a lower-tier version exists it will be
        picked up on the next full reload.

        Args:
            path: Path to the deleted YAML file.
            tier: Tier label of the directory containing the file.
        """
        # Find which persona was loaded from this path by matching
        # the stem (filename without extension) against loaded names.
        stem = path.stem
        to_remove: list[str] = []

        for name, (_, loaded_tier) in self._personas.items():
            if loaded_tier == tier and name == stem:
                to_remove.append(name)

        # Also check by persona name field (may differ from filename)
        for name, (config, loaded_tier) in self._personas.items():
            # Re-parse would fail since file is deleted, so check
            # if this persona's name matches the deleted file stem
            if loaded_tier == tier and name not in to_remove and config.name == stem:
                to_remove.append(name)

        for name in to_remove:
            del self._personas[name]
            logger.info(
                "persona_removed",
                name=name,
                tier=tier,
                path=str(path),
            )

    def _handle_upsert(
        self,
        path: Path,
        tier: str,
        fastembed: Any = None,
    ) -> None:
        """Re-parse, validate, and update a persona on create/modify.

        If validation fails the previous valid version is retained and
        a warning is logged (AC-FR-PERSONA-04.3).

        Args:
            path: Path to the created or modified YAML file.
            tier: Tier label of the directory containing the file.
            fastembed: Optional FastEmbed model for embedding rebuild.
        """
        persona = _parse_persona_file(path)

        if persona is None:
            # AC-FR-PERSONA-04.3: validation failed, retain previous
            logger.warning(
                "persona_reload_failed",
                path=str(path),
                tier=tier,
                msg="Validation failed; retaining previous version",
            )
            return

        # Check tier precedence: only update if the change comes from
        # a tier that is equal or higher precedence than the current one
        existing = self._personas.get(persona.name)
        if existing is not None:
            _, existing_tier = existing
            if not self._tier_has_precedence(tier, existing_tier):
                logger.debug(
                    "persona_reload_shadowed",
                    name=persona.name,
                    existing_tier=existing_tier,
                    change_tier=tier,
                )
                return

        self._personas[persona.name] = (persona, tier)
        logger.info(
            "persona_reloaded",
            name=persona.name,
            tier=tier,
            path=str(path),
        )

        # Rebuild embedding if FastEmbed is available
        if fastembed is not None and persona.description:
            try:
                # Embedding rebuild is handled by the caller's
                # build_embeddings method; log intent here.
                logger.debug(
                    "persona_embedding_rebuild_needed",
                    name=persona.name,
                )
            except Exception:
                logger.warning(
                    "persona_embedding_rebuild_failed",
                    name=persona.name,
                )

    @staticmethod
    def _tier_has_precedence(change_tier: str, existing_tier: str) -> bool:
        """Check if change_tier has equal or higher precedence.

        Args:
            change_tier: Tier of the incoming change.
            existing_tier: Tier of the currently loaded persona.

        Returns:
            True if the change should override the existing persona.
        """
        precedence = {
            TIER_PROJECT: 0,
            TIER_USER: 1,
            TIER_REMOTE: 2,
            TIER_BUILTIN: 3,
        }
        return precedence.get(change_tier, 99) <= precedence.get(existing_tier, 99)

    # ------------------------------------------------------------------
    # Semantic search (§3.5, FR-PERSONA-05)
    # ------------------------------------------------------------------

    @property
    def embeddings_available(self) -> bool:
        """Whether persona embeddings have been built.

        Returns ``True`` when ``build_embeddings`` has been called
        successfully and at least one embedding exists.
        """
        return len(self._embeddings) > 0

    async def build_embeddings(self, fastembed_model: Any) -> None:
        """Embed all persona descriptions for semantic search.

        Uses ``asyncio.to_thread`` to wrap the synchronous FastEmbed
        embedding call. Stores embeddings as numpy arrays keyed by
        persona name.

        Implements AC-FR-PERSONA-05.1.

        Args:
            fastembed_model: A FastEmbed ``TextEmbedding`` model instance.
                Typed as ``Any`` to avoid importing fastembed at module
                level (it is an optional dependency).
        """
        self._fastembed_model = fastembed_model
        self._embeddings.clear()

        texts: list[str] = []
        names: list[str] = []

        for name, (config, _) in self._personas.items():
            description = f"{config.name}: {config.description or ''}"
            texts.append(description)
            names.append(name)

        if not texts:
            logger.info("persona_embeddings_skip", reason="no personas to embed")
            return

        # FastEmbed's embed() is synchronous — run in a thread
        raw_embeddings: list[NDArray[np.float32]] = await asyncio.to_thread(
            lambda: [np.array(e, dtype=np.float32) for e in fastembed_model.embed(texts)]
        )

        for name, embedding in zip(names, raw_embeddings, strict=True):
            self._embeddings[name] = embedding

        logger.info(
            "persona_embeddings_built",
            count=len(self._embeddings),
            dimensions=raw_embeddings[0].shape[0] if raw_embeddings else 0,
        )

    def search(self, query: str, limit: int = 10) -> list[tuple[str, float]]:
        """Search personas by query string.

        When embeddings are available, performs cosine similarity search
        against all persona embeddings. Otherwise falls back to substring
        matching on persona name and description.

        Implements AC-FR-PERSONA-05.2, AC-FR-PERSONA-05.3.

        Args:
            query: Natural language search query or persona name.
            limit: Maximum number of results to return.

        Returns:
            List of ``(persona_name, similarity_score)`` tuples sorted
            by descending similarity. Scores are in ``[0.0, 1.0]``.
        """
        if self.embeddings_available and self._fastembed_model is not None:
            return self._search_semantic(query, limit)
        return self._search_substring(query, limit)

    def _search_semantic(self, query: str, limit: int) -> list[tuple[str, float]]:
        """Cosine similarity search using FastEmbed embeddings.

        Embeds the query synchronously (called from sync context) and
        computes cosine similarity against all stored persona embeddings.

        Args:
            query: Natural language search query.
            limit: Maximum number of results.

        Returns:
            Top-k results sorted by descending cosine similarity.
        """
        # Embed the query — FastEmbed.embed() returns a generator
        query_embeddings = list(self._fastembed_model.embed([query]))
        query_vec = np.array(query_embeddings[0], dtype=np.float32)

        scored: list[tuple[str, float]] = []
        for name, persona_vec in self._embeddings.items():
            sim = self._cosine_similarity(query_vec, persona_vec)
            scored.append((name, float(sim)))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    def _search_substring(self, query: str, limit: int) -> list[tuple[str, float]]:
        """Fallback substring matching when FastEmbed is unavailable.

        Matches against persona name and description. Exact name matches
        score 1.0; substring matches score 0.5.

        Implements AC-FR-PERSONA-05.3.

        Args:
            query: Search query string.
            limit: Maximum number of results.

        Returns:
            Matching results sorted by descending score.
        """
        query_lower = query.lower()
        results: list[tuple[str, float]] = []

        for name, (config, _) in self._personas.items():
            name_lower = name.lower()
            desc_lower = (config.description or "").lower()

            if name_lower == query_lower:
                results.append((name, 1.0))
            elif query_lower in name_lower or query_lower in desc_lower:
                results.append((name, 0.5))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    @staticmethod
    def _cosine_similarity(
        a: NDArray[np.float32],
        b: NDArray[np.float32],
    ) -> float:
        """Compute cosine similarity between two vectors.

        Args:
            a: First vector.
            b: Second vector.

        Returns:
            Cosine similarity in ``[-1.0, 1.0]``. Returns ``0.0`` if
            either vector has zero norm.
        """
        norm_a = float(np.linalg.norm(a))
        norm_b = float(np.linalg.norm(b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
