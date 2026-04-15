# Contributing to phraseturner

Thanks for your interest in contributing to phraseturner! This guide covers everything you need to get started.

## Prerequisites

- **Python ≥ 3.12**
- **[uv](https://docs.astral.sh/uv/)** — fast Python package manager
- **git**

## Development Setup

1. **Fork and clone the repository:**

   ```bash
   git clone https://github.com/<your-username>/phraseturner.git
   cd phraseturner
   ```

2. **Install all dependencies (runtime + dev):**

   ```bash
   uv sync
   ```

3. **Set up pre-commit hooks:**

   ```bash
   pre-commit install
   ```

4. **Download the spaCy NLP model:**

   ```bash
   uv run python -m spacy download en_core_web_sm
   ```

You're ready to go. The first time you run the server, optional models (FLAN-T5 ONNX, FastEmbed) will download automatically to `~/.cache/phraseturner/models/`.

## Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage (80% minimum enforced in CI)
uv run pytest --cov --cov-fail-under=80

# Property-based tests only
uv run pytest tests/test_properties.py

# Quick fail-fast mode
uv run pytest -x -q
```

## Code Style

phraseturner enforces strict code quality via [ruff](https://docs.astral.sh/ruff/) and [mypy](https://mypy-lang.org/).

### Linting and Formatting

We use ruff with 14 rule categories:

| Code | Category |
|------|----------|
| `E` | pycodestyle errors |
| `W` | pycodestyle warnings |
| `F` | pyflakes |
| `I` | isort (import sorting) |
| `B` | flake8-bugbear |
| `C4` | flake8-comprehensions |
| `UP` | pyupgrade |
| `N` | pep8-naming |
| `S` | flake8-bandit (security) |
| `SIM` | flake8-simplify |
| `TCH` | flake8-type-checking |
| `PTH` | flake8-use-pathlib |
| `RUF` | ruff-specific rules |
| `PL` | pylint |

Line length limit is **99 characters**.

```bash
# Check for lint issues
uv run ruff check .

# Auto-fix what can be fixed
uv run ruff check . --fix

# Format code
uv run ruff format .
```

### Type Checking

mypy runs in **strict mode**. All public APIs must have type hints — no exceptions.

```bash
uv run mypy --strict src/
```

Use Python 3.12+ type syntax:

```python
# Correct
def search(query: str, limit: int = 20) -> list[dict[str, str]]:
    ...

name: str | None = None

# Incorrect — don't use these
from typing import Optional, List, Dict
name: Optional[str] = None
```

### Documentation

- Use **Google-style docstrings** on all public functions.
- Internal/private functions (prefixed with `_`) don't need docstrings unless the logic is non-obvious.

```python
async def analyze_text(text: str, persona: str | None = None) -> AnalysisResult:
    """Analyse text quality against an optional persona.

    Args:
        text: The text to analyse (1–8000 tokens).
        persona: Persona name or semantic query for resolution.

    Returns:
        Structured analysis result with health score and per-sentence breakdown.

    Raises:
        TextTooLongError: If the input exceeds 8000 tokens.
    """
```

### Logging

Use `structlog` for all logging — never the stdlib `logging` module.

```python
import structlog

logger = structlog.get_logger()
logger.info("persona_loaded", name=persona.name, tier="built-in")
```

## Pre-commit Hooks

The following hooks run automatically on every commit:

| Hook | Purpose |
|------|---------|
| **ruff** | Lint checking with auto-fix |
| **ruff-format** | Code formatting |
| **mypy --strict** | Static type checking |
| **gitleaks** | Secret detection |
| **codespell** | Spell checking |

If a hook fails, fix the issue and re-stage your changes. You can run hooks manually:

```bash
# Run on staged files
pre-commit run

# Run on all files
pre-commit run --all-files
```

## Pull Request Process

1. **Fork the repo** and create a feature branch from `main`:

   ```bash
   git checkout -b feat/your-feature-name
   ```

2. **Write tests alongside your code.** New functionality needs corresponding tests — both unit tests and property-based tests where applicable.

3. **Ensure all checks pass** before pushing:

   ```bash
   uv run ruff check .
   uv run mypy --strict src/
   uv run pytest --cov --cov-fail-under=80
   ```

4. **Push and open a PR** against `main`. Fill in the PR template with:
   - A clear description of the change
   - What testing was done
   - Whether there are breaking changes

5. **Address review feedback** — all conversations must be resolved before merging.

## Commit Conventions

We follow [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix | Use for |
|--------|---------|
| `feat:` | New features |
| `fix:` | Bug fixes |
| `docs:` | Documentation changes |
| `test:` | Adding or updating tests |
| `refactor:` | Code changes that neither fix bugs nor add features |
| `chore:` | Maintenance tasks (deps, CI, config) |

Keep commits **focused and atomic** — one logical change per commit.

```bash
# Examples
git commit -m "feat: add tone dimension scoring to persona rules"
git commit -m "fix: handle empty text input in analyze tool"
git commit -m "docs: add persona authoring examples"
git commit -m "test: add property tests for health score aggregation"
```

## Project Structure

```
src/phraseturner/
├── __init__.py
├── __main__.py          # Entry point (mcp.run())
├── config.py            # ServerConfig (pydantic-settings)
├── exceptions.py        # Exception hierarchy
├── server.py            # FastMCP server + lifespan
├── models/              # Pydantic data models
├── personas/            # Persona system + built-in YAML files
├── pipeline/            # 6-stage analysis pipeline
└── t5/                  # FLAN-T5 integration
tests/
├── conftest.py
├── test_properties.py   # Hypothesis property-based tests
└── ...
```

## Questions?

Open an issue if something is unclear or you'd like to discuss a change before starting work.
