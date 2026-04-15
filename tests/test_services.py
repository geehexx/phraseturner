"""Tests for persona service functions (create_persona, validate_persona).

Validates: FR-TOOL-04, FR-TOOL-05, FR-PERSONA-09.
Design: §2.4, §3.6.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


import pytest

from phraseturner.config import ServerConfig
from phraseturner.exceptions import PersonaExistsError, PersonaValidationError
from phraseturner.models.persona import PersonaCreateResult, ValidationResult
from phraseturner.personas.index import PersonaIndex
from phraseturner.personas.services import create_persona, validate_persona

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_VALID_YAML = """\
name: test-persona
version: "1.0.0"
description: A test persona for unit tests.
tone:
  formality: 0.5
  confidence: 0.6
  warmth: 0.7
  directness: 0.5
  energy: 0.4
  verbosity: 0.3
rules:
  - id: no-jargon
    type: existence
    level: warning
    message: Avoid jargon.
    tokens:
      - synergy
      - leverage
"""

_INVALID_YAML_MISSING_NAME = """\
version: "1.0.0"
tone:
  formality: 0.5
"""

_INVALID_YAML_BAD_RANGE = """\
name: bad-range
version: "1.0.0"
tone:
  formality: 2.5
"""

_MALFORMED_YAML = "{{not: valid: yaml: [["


@pytest.fixture()
def user_dir(tmp_path: Path) -> Path:
    """Return a temporary user persona directory."""
    d = tmp_path / "personas"
    # Do NOT create it — services.py should create it (FR-PERSONA-09.2)
    return d


@pytest.fixture()
def config(user_dir: Path) -> ServerConfig:
    """Return a ServerConfig pointing to the temp user directory."""
    return ServerConfig(personas_dir=user_dir)


@pytest.fixture()
def persona_index(config: ServerConfig) -> PersonaIndex:
    """Return an empty PersonaIndex."""
    return PersonaIndex(config)


# ---------------------------------------------------------------------------
# validate_persona tests — FR-TOOL-05
# ---------------------------------------------------------------------------


class TestValidatePersona:
    """Tests for the validate_persona service function."""

    @pytest.mark.asyncio()
    async def test_valid_yaml_returns_valid_result(self) -> None:
        """Valid YAML produces a ValidationResult with valid=True."""
        result = await validate_persona(_VALID_YAML)

        assert isinstance(result, ValidationResult)
        assert result.valid is True
        assert result.errors == []

    @pytest.mark.asyncio()
    async def test_missing_required_field(self) -> None:
        """Missing 'name' field produces MISSING_REQUIRED_FIELD error."""
        result = await validate_persona(_INVALID_YAML_MISSING_NAME)

        assert result.valid is False
        codes = [e.code for e in result.errors]
        assert "MISSING_REQUIRED_FIELD" in codes

    @pytest.mark.asyncio()
    async def test_invalid_range(self) -> None:
        """Out-of-range tone dimension produces INVALID_RANGE error."""
        result = await validate_persona(_INVALID_YAML_BAD_RANGE)

        assert result.valid is False
        codes = [e.code for e in result.errors]
        assert "INVALID_RANGE" in codes

    @pytest.mark.asyncio()
    async def test_malformed_yaml(self) -> None:
        """Unparseable YAML produces INVALID_YAML error."""
        result = await validate_persona(_MALFORMED_YAML)

        assert result.valid is False
        assert len(result.errors) >= 1
        assert result.errors[0].code == "INVALID_YAML"

    @pytest.mark.asyncio()
    async def test_no_side_effects(self, tmp_path: Path) -> None:
        """validate_persona does not write any files."""
        before = set(tmp_path.rglob("*"))
        await validate_persona(_VALID_YAML)
        after = set(tmp_path.rglob("*"))
        assert before == after


# ---------------------------------------------------------------------------
# create_persona tests — FR-TOOL-04, FR-PERSONA-09
# ---------------------------------------------------------------------------


class TestCreatePersona:
    """Tests for the create_persona service function."""

    @pytest.mark.asyncio()
    async def test_creates_file_and_returns_result(
        self,
        config: ServerConfig,
        persona_index: PersonaIndex,
        user_dir: Path,
    ) -> None:
        """Valid YAML creates a file and returns PersonaCreateResult."""
        result = await create_persona(_VALID_YAML, config, persona_index)

        assert isinstance(result, PersonaCreateResult)
        assert result.name == "test-persona"
        assert result.validation.valid is True

        # File was written
        expected_path = user_dir / "test-persona.yaml"
        assert expected_path.exists()
        assert expected_path.read_text(encoding="utf-8") == _VALID_YAML

    @pytest.mark.asyncio()
    async def test_creates_user_directory_if_missing(
        self,
        config: ServerConfig,
        persona_index: PersonaIndex,
        user_dir: Path,
    ) -> None:
        """User directory is created when it does not exist (FR-PERSONA-09.2)."""
        assert not user_dir.exists()

        await create_persona(_VALID_YAML, config, persona_index)

        assert user_dir.is_dir()

    @pytest.mark.asyncio()
    async def test_registers_in_index(
        self,
        config: ServerConfig,
        persona_index: PersonaIndex,
    ) -> None:
        """Created persona is added to the PersonaIndex."""
        assert persona_index.count == 0

        await create_persona(_VALID_YAML, config, persona_index)

        assert persona_index.count == 1
        persona = persona_index.get("test-persona")
        assert persona.name == "test-persona"

    @pytest.mark.asyncio()
    async def test_duplicate_raises_persona_exists(
        self,
        config: ServerConfig,
        persona_index: PersonaIndex,
    ) -> None:
        """Creating the same persona twice raises PersonaExistsError."""
        await create_persona(_VALID_YAML, config, persona_index)

        with pytest.raises(PersonaExistsError) as exc_info:
            await create_persona(_VALID_YAML, config, persona_index)

        assert exc_info.value.code == "PERSONA_EXISTS"

    @pytest.mark.asyncio()
    async def test_invalid_yaml_raises_validation_error(
        self,
        config: ServerConfig,
        persona_index: PersonaIndex,
    ) -> None:
        """Invalid YAML raises PersonaValidationError."""
        with pytest.raises(PersonaValidationError) as exc_info:
            await create_persona(_INVALID_YAML_MISSING_NAME, config, persona_index)

        assert exc_info.value.code == "PERSONA_VALIDATION_FAILED"
        assert persona_index.count == 0

    @pytest.mark.asyncio()
    async def test_malformed_yaml_raises_validation_error(
        self,
        config: ServerConfig,
        persona_index: PersonaIndex,
    ) -> None:
        """Malformed YAML raises PersonaValidationError."""
        with pytest.raises(PersonaValidationError):
            await create_persona(_MALFORMED_YAML, config, persona_index)

    @pytest.mark.asyncio()
    async def test_file_path_in_result(
        self,
        config: ServerConfig,
        persona_index: PersonaIndex,
        user_dir: Path,
    ) -> None:
        """Result file_path matches the expected user directory location."""
        result = await create_persona(_VALID_YAML, config, persona_index)

        assert result.file_path == str(user_dir / "test-persona.yaml")

    @pytest.mark.asyncio()
    async def test_default_user_dir_when_config_unset(
        self,
        persona_index: PersonaIndex,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Falls back to ~/.config/phraseturner/personas/ when personas_dir is None."""
        # Override HOME so we don't write to the real home directory
        fake_home = tmp_path / "fakehome"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        config_no_dir = ServerConfig(personas_dir=None)
        # Re-create index with this config
        idx = PersonaIndex(config_no_dir)

        result = await create_persona(_VALID_YAML, config_no_dir, idx)

        expected_dir = fake_home / ".config" / "phraseturner" / "personas"
        assert expected_dir.is_dir()
        assert result.file_path == str(expected_dir / "test-persona.yaml")
