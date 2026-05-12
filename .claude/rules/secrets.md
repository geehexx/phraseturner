# Secrets Management

## The Rule: Never Hardcode

```python
# ❌ Wrong
NOVA_ACT_API_KEY = "act-abc123..."
AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"

# ✅ Correct: read from env via pydantic-settings
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    nova_act_api_key: str
    exa_api_key: str
    aws_default_region: str = "us-east-1"
```

## Local development — `.env` + `.envrc`

Local secrets go in `.env` (Python code reads via `python-dotenv` or `BaseSettings`) and `.envrc` (direnv, for shell + MCP servers). Both are gitignored.

```bash
# .envrc — never committed, direnv auto-loads
export EXA_API_KEY=bb11c270-...
export NOVA_ACT_API_KEY=act-...
export AWS_DEFAULT_REGION=us-east-1
```

```bash
# .env — candidate profile, also gitignored
LINKEDIN_URL=https://linkedin.com/in/...
CANDIDATE_NAME=Andrew Crozier
CANDIDATE_EMAIL=andrew.crozier@t-3.ai
AWS_DEFAULT_REGION=eu-west-2
```

`.env.example` — committed template with placeholder values.

## AWS credentials

Never copy AWS keys into `.env` or project files. They live in `~/.aws/credentials` (shared with boto3 / AWS CLI). boto3 auto-loads them; set `AWS_DEFAULT_REGION` only.

## GitHub Actions secrets

Stored as repo secrets, referenced in workflow YAML:
```yaml
env:
  NOVA_ACT_API_KEY: ${{ secrets.NOVA_ACT_API_KEY }}
  EXA_API_KEY: ${{ secrets.EXA_API_KEY }}
```

## gitleaks — pre-commit scanning

Runs automatically via pre-commit hook. If gitleaks fires on a false positive:

```toml
# .gitleaksignore
# Local-only placeholder, not a real key
path = ".env.example"
```

Never bypass gitleaks with `--no-verify` or `SKIP=gitleaks`.

## If a secret is accidentally committed

1. Do NOT push. `git reset HEAD~1` to undo.
2. **Rotate the credential immediately** — assume it's compromised.
3. Add the file pattern to `.gitignore`.
4. Force-push is NOT sufficient — rotation is mandatory.
5. Run `gitleaks detect --verbose` to confirm no other leaks.

## Rotation checklist

When a secret expires or rotates:
1. Identify all locations — `.env`, `.envrc`, GitHub Actions secrets, any MCP configs.
2. Generate new secret at the source service.
3. Update all locations simultaneously to avoid downtime.
4. Verify each location works with the new secret.

## Anti-patterns

- Hardcoding API keys in source (caught by bandit pre-commit)
- Logging secrets — never `logger.info(f"API key: {key}")`; reference by key name only
- Committing `.env` / `.envrc` — both gitignored; if accidentally staged, `git reset HEAD .env` immediately
- Using `$PATH` or `$HOME` in MCP server bash commands (Kiro/Claude Code path-expansion trap)
