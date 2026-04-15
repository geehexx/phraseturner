"""Tests for the 4-tier persona directory loader and PersonaIndex.

Validates: FR-PERSONA-01, NFR-SEC-02.
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path

import pytest
import yaml

from phraseturner.config import ServerConfig
from phraseturner.exceptions import PersonaNotFoundError
from phraseturner.personas.index import (
    TIER_BUILTIN,
    TIER_PROJECT,
    TIER_USER,
    PersonaIndex,
    _parse_persona_file,
    get_persona_directories,
)

# ---------------------------------------------------------------------------
# Minimal valid persona YAML for testing
# ---------------------------------------------------------------------------

_MINIMAL_PERSONA = {
    "name": "test-persona",
    "version": "1.0.0",
    "description": "A test persona.",
}


def _write_persona_yaml(directory: Path, data: dict[str, object]) -> Path:
    """Write a persona YAML file and return its path."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{data['name']}.yaml"
    path.write_text(yaml.dump(data), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# get_persona_directories
# ---------------------------------------------------------------------------


class TestGetPersonaDirectories:
    """Tests for get_persona_directories()."""

    def test_always_includes_user_and_builtin(self, tmp_path: Path) -> None:
        """User and built-in tiers are always present."""
        config = ServerConfig(personas_dir=tmp_path / "user-personas")
        dirs = get_persona_directories(config)
        tiers = [tier for _, tier in dirs]
        assert TIER_USER in tiers
        assert TIER_BUILTIN in tiers

    def test_user_dir_created_if_missing(self, tmp_path: Path) -> None:
        """AC-FR-PERSONA-09.2: user dir is created on first call."""
        user_dir = tmp_path / "new-user-dir"
        assert not user_dir.exists()
        config = ServerConfig(personas_dir=user_dir)
        get_persona_directories(config)
        assert user_dir.is_dir()

    def test_project_dir_included_when_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AC-FR-PERSONA-01.3: project tier included when .phraseturner/personas/ exists."""
        project_personas = tmp_path / ".phraseturner" / "personas"
        project_personas.mkdir(parents=True)
        monkeypatch.chdir(tmp_path)
        config = ServerConfig(personas_dir=tmp_path / "user")
        dirs = get_persona_directories(config)
        tiers = [tier for _, tier in dirs]
        assert tiers[0] == TIER_PROJECT

    def test_project_dir_excluded_when_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Project tier excluded when directory does not exist."""
        monkeypatch.chdir(tmp_path)
        config = ServerConfig(personas_dir=tmp_path / "user")
        dirs = get_persona_directories(config)
        tiers = [tier for _, tier in dirs]
        assert TIER_PROJECT not in tiers

    def test_precedence_order(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AC-FR-PERSONA-01.1: project → user → built-in precedence."""
        project_personas = tmp_path / ".phraseturner" / "personas"
        project_personas.mkdir(parents=True)
        monkeypatch.chdir(tmp_path)
        config = ServerConfig(personas_dir=tmp_path / "user")
        dirs = get_persona_directories(config)
        tiers = [tier for _, tier in dirs]
        assert tiers.index(TIER_PROJECT) < tiers.index(TIER_USER)
        assert tiers.index(TIER_USER) < tiers.index(TIER_BUILTIN)


# ---------------------------------------------------------------------------
# _parse_persona_file
# ---------------------------------------------------------------------------


class TestParsePersonaFile:
    """Tests for _parse_persona_file()."""

    def test_valid_yaml(self, tmp_path: Path) -> None:
        """Valid YAML returns a PersonaConfig."""
        path = _write_persona_yaml(tmp_path, _MINIMAL_PERSONA)
        result = _parse_persona_file(path)
        assert result is not None
        assert result.name == "test-persona"
        assert result.version == "1.0.0"

    def test_invalid_yaml_returns_none(self, tmp_path: Path) -> None:
        """Malformed YAML returns None (logged warning, no crash)."""
        path = tmp_path / "bad.yaml"
        path.write_text("{{invalid yaml", encoding="utf-8")
        assert _parse_persona_file(path) is None

    def test_non_dict_yaml_returns_none(self, tmp_path: Path) -> None:
        """YAML that parses to a non-dict returns None."""
        path = tmp_path / "list.yaml"
        path.write_text("- item1\n- item2\n", encoding="utf-8")
        assert _parse_persona_file(path) is None

    def test_validation_failure_returns_none(self, tmp_path: Path) -> None:
        """YAML that fails Pydantic validation returns None."""
        path = tmp_path / "invalid.yaml"
        path.write_text(yaml.dump({"name": "x"}), encoding="utf-8")
        # Missing required 'version' field
        assert _parse_persona_file(path) is None

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        """Non-existent file returns None."""
        assert _parse_persona_file(tmp_path / "nope.yaml") is None

    def test_uses_safe_load(self, tmp_path: Path) -> None:
        """NFR-SEC-02: only yaml.safe_load is used (no arbitrary code exec)."""
        # A YAML file with a Python object tag should fail with safe_load
        path = tmp_path / "unsafe.yaml"
        path.write_text(
            "!!python/object:os.system ['echo pwned']",
            encoding="utf-8",
        )
        assert _parse_persona_file(path) is None


# ---------------------------------------------------------------------------
# PersonaIndex
# ---------------------------------------------------------------------------


class TestPersonaIndex:
    """Tests for PersonaIndex class."""

    @pytest.fixture()
    def user_dir(self, tmp_path: Path) -> Path:
        """Create a temporary user persona directory."""
        d = tmp_path / "user-personas"
        d.mkdir()
        return d

    @pytest.fixture()
    def config(self, user_dir: Path) -> ServerConfig:
        """ServerConfig pointing to the temp user directory."""
        return ServerConfig(personas_dir=user_dir)

    @pytest.mark.asyncio()
    async def test_load_all_empty(self, config: ServerConfig) -> None:
        """Loading with no user YAML files still loads built-in personas."""
        index = PersonaIndex(config)
        await index.load_all()
        # Built-in personas are always loaded (9 shipped with the package)
        builtin_count = sum(
            1 for p in index.list_all() if index.get_tier(p.name) == TIER_BUILTIN
        )
        assert index.count == builtin_count
        assert all(index.get_tier(p.name) == TIER_BUILTIN for p in index.list_all())

    @pytest.mark.asyncio()
    async def test_load_single_persona(
        self, config: ServerConfig, user_dir: Path,
    ) -> None:
        """A single valid persona is loaded and retrievable."""
        _write_persona_yaml(user_dir, _MINIMAL_PERSONA)
        index = PersonaIndex(config)
        await index.load_all()
        # 1 user persona + 9 built-in personas
        user_personas = [p for p in index.list_all() if index.get_tier(p.name) == TIER_USER]
        assert len(user_personas) == 1
        persona = index.get("test-persona")
        assert persona.name == "test-persona"
        assert index.get_tier("test-persona") == TIER_USER

    @pytest.mark.asyncio()
    async def test_higher_tier_wins_on_collision(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AC-FR-PERSONA-01.2: higher-tier persona wins on name collision."""
        # Set up project tier
        project_dir = tmp_path / ".phraseturner" / "personas"
        project_persona = {**_MINIMAL_PERSONA, "description": "project version"}
        _write_persona_yaml(project_dir, project_persona)

        # Set up user tier
        user_dir = tmp_path / "user-personas"
        user_persona = {**_MINIMAL_PERSONA, "description": "user version"}
        _write_persona_yaml(user_dir, user_persona)

        monkeypatch.chdir(tmp_path)
        config = ServerConfig(personas_dir=user_dir)
        index = PersonaIndex(config)
        await index.load_all()

        # Project tier should win
        persona = index.get("test-persona")
        assert persona.description == "project version"
        assert index.get_tier("test-persona") == TIER_PROJECT

    @pytest.mark.asyncio()
    async def test_get_raises_not_found(self, config: ServerConfig) -> None:
        """get() raises PersonaNotFoundError for unknown names."""
        index = PersonaIndex(config)
        await index.load_all()
        with pytest.raises(PersonaNotFoundError):
            index.get("nonexistent")

    @pytest.mark.asyncio()
    async def test_get_tier_raises_not_found(
        self, config: ServerConfig,
    ) -> None:
        """get_tier() raises PersonaNotFoundError for unknown names."""
        index = PersonaIndex(config)
        await index.load_all()
        with pytest.raises(PersonaNotFoundError):
            index.get_tier("nonexistent")

    @pytest.mark.asyncio()
    async def test_list_all_returns_all(
        self, config: ServerConfig, user_dir: Path,
    ) -> None:
        """list_all() returns all loaded personas (user + built-in)."""
        for i in range(3):
            _write_persona_yaml(
                user_dir,
                {"name": f"persona-{i}", "version": "1.0.0"},
            )
        index = PersonaIndex(config)
        await index.load_all()
        user_personas = [p for p in index.list_all() if index.get_tier(p.name) == TIER_USER]
        assert len(user_personas) == 3
        names = {p.name for p in user_personas}
        assert names == {"persona-0", "persona-1", "persona-2"}

    @pytest.mark.asyncio()
    async def test_invalid_files_skipped(
        self, config: ServerConfig, user_dir: Path,
    ) -> None:
        """Invalid YAML files are skipped without crashing."""
        _write_persona_yaml(user_dir, _MINIMAL_PERSONA)
        (user_dir / "broken.yaml").write_text("{{bad", encoding="utf-8")
        index = PersonaIndex(config)
        await index.load_all()
        user_personas = [p for p in index.list_all() if index.get_tier(p.name) == TIER_USER]
        assert len(user_personas) == 1

    @pytest.mark.asyncio()
    async def test_load_all_clears_previous(
        self, config: ServerConfig, user_dir: Path,
    ) -> None:
        """Calling load_all() again replaces the previous index."""
        _write_persona_yaml(user_dir, _MINIMAL_PERSONA)
        index = PersonaIndex(config)
        await index.load_all()
        user_count_before = sum(
            1 for p in index.list_all() if index.get_tier(p.name) == TIER_USER
        )
        assert user_count_before == 1

        # Remove the file and reload
        (user_dir / "test-persona.yaml").unlink()
        await index.load_all()
        user_count_after = sum(
            1 for p in index.list_all() if index.get_tier(p.name) == TIER_USER
        )
        assert user_count_after == 0

    @pytest.mark.asyncio()
    async def test_yml_extension_supported(
        self, config: ServerConfig, user_dir: Path,
    ) -> None:
        """Both .yaml and .yml extensions are supported."""
        data = {"name": "yml-persona", "version": "1.0.0"}
        path = user_dir / "yml-persona.yml"
        path.write_text(yaml.dump(data), encoding="utf-8")
        index = PersonaIndex(config)
        await index.load_all()
        user_personas = [p for p in index.list_all() if index.get_tier(p.name) == TIER_USER]
        assert len(user_personas) == 1
        assert index.get("yml-persona").name == "yml-persona"


# ---------------------------------------------------------------------------
# Hot-reload: watch_for_changes (§3.4, FR-PERSONA-04)
# ---------------------------------------------------------------------------


class TestPathToTier:
    """Tests for PersonaIndex._path_to_tier()."""

    def test_resolves_user_tier(self, tmp_path: Path) -> None:
        """A path inside the user directory resolves to 'user'."""
        user_dir = tmp_path / "user-personas"
        user_dir.mkdir()
        config = ServerConfig(personas_dir=user_dir)
        index = PersonaIndex(config)
        path = user_dir / "some-persona.yaml"
        assert index._path_to_tier(path) == TIER_USER

    def test_resolves_builtin_tier(self, tmp_path: Path) -> None:
        """A path inside the built-in directory resolves to 'built-in'."""
        user_dir = tmp_path / "user-personas"
        user_dir.mkdir()
        config = ServerConfig(personas_dir=user_dir)
        index = PersonaIndex(config)
        builtin_dir = Path(__file__).parent.parent / "src" / "phraseturner" / "personas"
        if builtin_dir.is_dir():
            path = builtin_dir / "test.yaml"
            assert index._path_to_tier(path) == TIER_BUILTIN

    def test_unknown_path(self, tmp_path: Path) -> None:
        """A path outside all persona directories returns 'unknown'."""
        user_dir = tmp_path / "user-personas"
        user_dir.mkdir()
        config = ServerConfig(personas_dir=user_dir)
        index = PersonaIndex(config)
        assert index._path_to_tier(Path("/some/random/path.yaml")) == "unknown"


class TestTierHasPrecedence:
    """Tests for PersonaIndex._tier_has_precedence()."""

    def test_project_over_user(self) -> None:
        assert PersonaIndex._tier_has_precedence(TIER_PROJECT, TIER_USER) is True

    def test_user_over_builtin(self) -> None:
        assert PersonaIndex._tier_has_precedence(TIER_USER, TIER_BUILTIN) is True

    def test_builtin_not_over_project(self) -> None:
        assert PersonaIndex._tier_has_precedence(TIER_BUILTIN, TIER_PROJECT) is False

    def test_same_tier(self) -> None:
        assert PersonaIndex._tier_has_precedence(TIER_USER, TIER_USER) is True


class TestHandleUpsert:
    """Tests for PersonaIndex._handle_upsert()."""

    @pytest.fixture()
    def user_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "user-personas"
        d.mkdir()
        return d

    @pytest.fixture()
    def config(self, user_dir: Path) -> ServerConfig:
        return ServerConfig(personas_dir=user_dir)

    def test_upsert_new_persona(
        self, config: ServerConfig, user_dir: Path,
    ) -> None:
        """A new valid persona file is added to the index."""
        path = _write_persona_yaml(user_dir, _MINIMAL_PERSONA)
        index = PersonaIndex(config)
        index._handle_upsert(path, TIER_USER)
        assert index.count == 1
        assert index.get("test-persona").name == "test-persona"

    def test_upsert_invalid_retains_previous(
        self, config: ServerConfig, user_dir: Path,
    ) -> None:
        """AC-FR-PERSONA-04.3: invalid file retains previous version."""
        # Load a valid persona first
        path = _write_persona_yaml(user_dir, _MINIMAL_PERSONA)
        index = PersonaIndex(config)
        index._handle_upsert(path, TIER_USER)
        assert index.count == 1

        # Overwrite with invalid content
        path.write_text("{{invalid yaml", encoding="utf-8")
        index._handle_upsert(path, TIER_USER)

        # Previous version retained
        assert index.count == 1
        assert index.get("test-persona").name == "test-persona"

    def test_upsert_lower_tier_does_not_override(
        self, config: ServerConfig, user_dir: Path,
    ) -> None:
        """A lower-tier change does not override a higher-tier persona."""
        index = PersonaIndex(config)
        # Simulate a project-tier persona already loaded
        path = _write_persona_yaml(user_dir, _MINIMAL_PERSONA)
        index._handle_upsert(path, TIER_PROJECT)

        # Now try to upsert from built-in tier
        index._handle_upsert(path, TIER_BUILTIN)

        # Project tier should still be the loaded tier
        assert index.get_tier("test-persona") == TIER_PROJECT


class TestHandleDeleted:
    """Tests for PersonaIndex._handle_deleted()."""

    @pytest.fixture()
    def user_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "user-personas"
        d.mkdir()
        return d

    @pytest.fixture()
    def config(self, user_dir: Path) -> ServerConfig:
        return ServerConfig(personas_dir=user_dir)

    def test_delete_removes_persona(
        self, config: ServerConfig, user_dir: Path,
    ) -> None:
        """Deleting a file removes the persona from the index."""
        path = _write_persona_yaml(user_dir, _MINIMAL_PERSONA)
        index = PersonaIndex(config)
        index._handle_upsert(path, TIER_USER)
        assert index.count == 1

        index._handle_deleted(path, TIER_USER)
        assert index.count == 0

    def test_delete_wrong_tier_no_effect(
        self, config: ServerConfig, user_dir: Path,
    ) -> None:
        """Deleting from a different tier has no effect."""
        path = _write_persona_yaml(user_dir, _MINIMAL_PERSONA)
        index = PersonaIndex(config)
        index._handle_upsert(path, TIER_USER)
        assert index.count == 1

        # Try to delete from built-in tier — should not remove
        index._handle_deleted(path, TIER_BUILTIN)
        assert index.count == 1

    def test_delete_nonexistent_no_crash(
        self, config: ServerConfig, user_dir: Path,
    ) -> None:
        """Deleting a file that was never loaded does not crash."""
        index = PersonaIndex(config)
        index._handle_deleted(user_dir / "nope.yaml", TIER_USER)
        assert index.count == 0


class TestWatchForChanges:
    """Integration tests for watch_for_changes (FR-PERSONA-04)."""

    @pytest.fixture()
    def user_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "user-personas"
        d.mkdir()
        return d

    @pytest.fixture()
    def config(self, user_dir: Path) -> ServerConfig:
        return ServerConfig(
            personas_dir=user_dir,
            watch_debounce_ms=100,  # Faster for tests
        )

    @pytest.mark.asyncio()
    async def test_detects_new_file(
        self, config: ServerConfig, user_dir: Path,
    ) -> None:
        """AC-FR-PERSONA-04.1: new persona file is detected and loaded."""

        index = PersonaIndex(config)
        await index.load_all()
        assert index.count >= 0  # May have built-ins

        initial_count = index.count
        task = asyncio.create_task(index.watch_for_changes())

        # Give the watcher time to start
        await asyncio.sleep(0.3)

        # Create a new persona file
        _write_persona_yaml(user_dir, _MINIMAL_PERSONA)

        # Wait for debounce + processing
        await asyncio.sleep(0.5)

        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

        assert index.count == initial_count + 1
        assert index.get("test-persona").name == "test-persona"

    @pytest.mark.asyncio()
    async def test_graceful_cancellation(
        self, config: ServerConfig,
    ) -> None:
        """Watch task handles CancelledError gracefully."""

        index = PersonaIndex(config)
        task = asyncio.create_task(index.watch_for_changes())
        await asyncio.sleep(0.2)
        task.cancel()
        # Should not raise — CancelledError is caught internally
        with contextlib.suppress(asyncio.CancelledError):
            await task

    @pytest.mark.asyncio()
    async def test_ignores_non_yaml_files(
        self, config: ServerConfig, user_dir: Path,
    ) -> None:
        """Non-YAML files are ignored by the watcher."""

        index = PersonaIndex(config)
        await index.load_all()
        initial_count = index.count

        task = asyncio.create_task(index.watch_for_changes())
        await asyncio.sleep(0.3)

        # Create a non-YAML file
        (user_dir / "readme.txt").write_text("not a persona", encoding="utf-8")
        await asyncio.sleep(0.5)

        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

        assert index.count == initial_count
