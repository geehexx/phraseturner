# Shell Usage

## Command classification

| Task | Tool | Notes |
|------|------|-------|
| Python packages | `uv add` / `uv run` | NEVER `pip install` |
| Tests | `uv run pytest` | testmon cached |
| Linting | `uv run ruff check` | NEVER black/flake8/isort |
| Type check | `uv run mypy src/` | |
| CLI entry | `uv run cv ...` | |
| spaCy model | `uv run python -m spacy download en_core_web_sm` | one-time |

## Timeout reference

| Operation | Timeout |
|-----------|---------|
| Quick commands | 30s |
| `uv sync` | 120s |
| pytest unit | 120s |
| pytest full | 300s |
| Nova Act scrape | 600s |

## Long-running operations

- Dev servers / watchers: background, never `shell_exec` with no timeout.
- Reindex / embed jobs: detached tmux so they survive session exit.

```bash
# Detached tmux for zombie-safe long-running job
tmux new -d -s my-job "nice -n 15 long_command 2>&1 | tee /tmp/my-job.log"
```

## Git stash coordination

Always use a descriptive message:
```bash
git stash push -m "WIP: feat/my-branch — stashing for hotfix; resume with git stash pop stash@{0}"
```

## Secrets audit before commit

```bash
git diff --cached --name-only | xargs -I{} grep -l \
  -e 'NOVA_ACT_API_KEY' -e 'EXA_API_KEY' -e 'AWS_SECRET' -e 'password\s*=' {} 2>/dev/null
```

## External API safety

```bash
timeout 30 curl -s https://api.example.com/endpoint   # always timeout
```

Python: always set `timeout=` on `httpx.AsyncClient` calls.

## Run commands once

```bash
uv run pytest tests/unit/ -q 2>&1 | tee /tmp/test-output.txt
# Then read /tmp/test-output.txt — don't re-run the same command to "verify"
```
