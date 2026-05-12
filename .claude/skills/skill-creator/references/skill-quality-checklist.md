# Skill Quality Checklist

Detailed quality criteria for new and updated skills in `.claude/skills/`. Load this file when authoring a skill — it is the checklist the `skill-creator` SKILL.md points at.

## Frontmatter Checklist

- [ ] `name` matches the folder name exactly
- [ ] `name` is lowercase, numbers, hyphens only, max 64 chars
- [ ] `description` is present and non-empty
- [ ] `description` is ≤1024 chars (Kiro hard limit — silent truncation breaks matching)
- [ ] `description` contains `Activates on:` with ≥5 trigger phrases
- [ ] `description` is ≥100 words (semantic match reliability floor)
- [ ] `metadata` block present with `category`, `complexity`, `activation_examples`
- [ ] `activation_examples` has ≥3 entries (natural language queries)

**Measuring description length:**

```python
desc = """..."""
assert len(desc) <= 1024
assert len(desc.split()) >= 100
assert "Activates on:" in desc
triggers = [t.strip() for t in desc.split("Activates on:")[1].split(",") if t.strip()]
assert len(triggers) >= 5
```

The `scripts/verify-skill-quality.py` script automates all six checks.

## Content Checklist

- [ ] Content is substantive — actual workflow steps, not just bullet points
- [ ] Each step has at least one tool call with real parameters
- [ ] Tool names are current (Read, Write, Edit, Bash) — not legacy `readFile`/`grepSearch`
- [ ] cv-builder-specific context included (ADR references, project conventions)
- [ ] No placeholder content (`TODO: add examples`, `implement later`)
- [ ] No internal tooling references in user-facing content (no `memory://`, no `.claude/` paths as implementation detail)

## Sub-Files Policy (Scoped to Workspace)

**ALLOWED** (workspace skills at `.claude/skills/{name}/`):

- `references/*.md` (top-level only, no nesting)
- `scripts/*.{py,sh}`
- `assets/*`

**REQUIRED when using sub-files:**

- SKILL.md cites absolute paths: `.claude/skills/{name}/references/foo.md`
- NOT relative: `references/foo.md`
- SKILL.md body stays <500 lines (soft cap — Anthropic progressive-disclosure guidance)

**PROHIBITED:**

- Global skills at `~/.claude/skills/` with `references/` (Kiro bug #6955 — relative paths fail to resolve)
- Nested references (`references/foo/bar.md`) — causes progressive-disclosure previews to miss content
- Non-markdown files in `references/` — move scripts into `scripts/`, binaries into `assets/`

## Structure Checklist

- [ ] `When to Activate` section present
- [ ] Steps are numbered and named
- [ ] `cv-builder-Specific Patterns` section present when applicable
- [ ] Code blocks use correct language tags (` ```python `, ` ```bash `, ` ```yaml `)

## Tool Call Examples (Current Names)

```python
# File operations
Read(path="path/to/file.md")
Bash (grep/rg)(pattern="pattern", path="dir/", include="**/*.py")
Write(path="path/to/file.md", content="...")
Edit(path="file.py", old_str="old", new_str="new")

# Dev operations
Bash(command="uv run poe test-backend")
Bash (python)(code="print('hello')")
Bash (git status)()
Bash (pytest)(path="backend/tests/unit/")

# Memory
mcp_basic_memory_search_notes(query="topic keywords")
mcp_basic_memory_write_note(title="note-title", directory="dir", content="...")
```

## Anti-Patterns to Avoid

```python
# Wrong — outdated tool names
readFile("path/to/file")
grepSearch("pattern")
executePwsh("command")

# Wrong — Kiro built-in tools (these names are legacy)
listDirectory("path")
strReplace("file", "old", "new")

# Wrong — pip instead of uv
pip install package-name

# Wrong — npm instead of pnpm
npm install

# Wrong — black/flake8 instead of ruff
black src/
flake8 src/

# Wrong — terraform instead of cdk
terraform plan
```

## Adapting Community Skills — British English & cv-builder Conventions

When adapting from `anthropics/skills`, `obra/superpowers`, or `ComposioHQ/awesome-claude-skills`:

1. **British English in taxonomy content**: color → colour, organization → organisation, analyze → analyse, behavior → behaviour
2. **Tool name mapping**: replace generic tool names with current Claude Code names (Read, Write, Edit, Bash) and cv-builder MCP prefixes (`mcp__basic-memory__*`, `mcp__basic-memory__*`, `mcp__exa__*`, `mcp__context7__*`)
3. **Project conventions**:
   - `uv` for Python packages (never `pip`)
   - `pnpm` for frontend (never `npm` / `yarn`)
   - `ruff` for lint (never `black` / `flake8` / `isort`)
   - `cdk` for infra (never `terraform` / `tofu`)
4. **Attribution**: note the source in the skill's intro paragraph. Example: `Adapted from garrytan/gstack (MIT).`
5. **ADR cross-links**: add links to relevant ADRs in `docs/adrs/` where the skill touches architectural decisions.

## Category Guide

| Category | Examples |
|----------|----------|
| `planning` | Feature planning, spec creation, architecture review |
| `quality` | Drift analysis, delivery validation, doc review |
| `security` | Security audit, auth review, secrets check |
| `testing` | Test writing, coverage analysis, browser testing |
| `deployment` | Release, deploy, infrastructure changes |
| `meta` | Skills about skills, MCP tools, Kiro configuration |
| `domain-specific` | cv-builder-specific workflows (search tuning, taxonomy enrichment) |

## Complexity Guide

| Complexity | Meaning | Examples |
|-----------:|---------|----------|
| 1 | Trivial | Linter toggle, formatter preference |
| 2 | Simple | Single-file template generation, commit message formatter |
| 3 | Moderate | Multi-step workflow with decisions (skill-creator, investigate) |
| 4 | Complex | Cross-domain workflow with HITL gates (deploy, cut-release) |
| 5 | Major | System-spanning workflows requiring multi-agent dispatch |

## Skill vs Steering Decision Table

| Content type | Use skill | Use steering rule |
|--------------|:---------:|:-----------------:|
| User-invoked workflow with steps | Yes | No |
| Always-relevant conventions | No | Yes (always-on) |
| Domain-specific patterns agents follow automatically | No | Yes (auto-scoped) |
| Procedure a user explicitly asks for | Yes | No |
| Agent behaviour rules | No | Yes |
| Recurring multi-step process | Yes | No |
| Code quality standards | No | Yes |

**Decision rule**: if the user would explicitly say "do the X workflow", it is a skill. If the agent should follow the pattern automatically without being asked, it is a steering rule.

**If steering already covers it**: update the steering file with better examples rather than creating a new skill. Steering updates are cheaper to maintain and apply automatically.
