---
name: skill-creator
description: "Creates new Kiro skills following the Agent Skills standard and cv-builder quality requirements. Guides the full skill creation workflow: research the source community repository (anthropics/skills, obra/superpowers, agentsys), check if existing steering already covers the workflow, design the SKILL.md frontmatter with keyword-rich description under 1024 chars, write substantive body content with actual tool calls and cv-builder-specific patterns, add discovery metadata with activation examples, and verify quality with the manual check script. Includes the Skill vs Steering decision table and adaptation guidelines for British English and current tool names. Use when adding new skills to the .claude/skills/ library. Activates on: create a skill, new skill, add skill, skill authoring, build a skill, write a skill, create SKILL.md, add to skill library."
metadata:
  category: meta
  complexity: 2
  activation_examples:
    - "create a new skill for the pre-mortem workflow"
    - "add a skill for the CDK deployment process"
    - "write a SKILL.md for the stakeholder communication workflow"
    - "build a skill based on the gstack retro pattern"
    - "create a skill that helps with Nova Act stealth audits"
  related_steering:
    - kiro-meta-guide
---

# Skill Creator Skill

Creates new Kiro skills following the Agent Skills standard and cv-builder quality requirements. Adapted from Anthropic skills (Apache 2.0). Use this skill to add new skills to the `.claude/skills/` library.

## When to Activate

- You want to capture a recurring workflow as a reusable skill
- You've found a useful skill in a community repository (anthropics/skills, obra/superpowers, agentsys)
- A workflow is being repeated across multiple sessions and should be standardised
- A steering file is getting too long and a specific workflow should be extracted as a skill
- You want to adapt a community skill to cv-builder conventions

## Step 1: Research the Source

If adapting from a community skill, read the original before writing anything.

**Known community repositories**:

| Repository | Focus | How to browse |
|-----------|-------|---------------|
| `anthropics/skills` | Official Anthropic skills — TDD, brainstorming, prompt engineering | `gh api /repos/anthropics/skills/contents/` |
| `obra/superpowers` | Agentic skills: brainstorm → plan → TDD → subagent → review | `gh api /repos/obra/superpowers/contents/` |
| `ComposioHQ/awesome-claude-skills` | 78+ SaaS automation skills via Composio | `gh api /repos/ComposioHQ/awesome-claude-skills/contents/` |
| `gkhantyln/kiro-professional-toolkit` | 50 skills, 34 agents, 22 steering files | `gh api /repos/gkhantyln/kiro-professional-toolkit/contents/` |

**Check basic-memory first** — prior research may already be catalogued:

```python
mcp_basic_memory_search_notes(query="kiro skills community {topic}")
```

**Browse a repository**:

```python
Bash(
    command="gh api /repos/anthropics/skills/contents/ | python3 -m json.tool | grep name"
)
```

**Read a specific skill**:

```python
Bash(
    command="gh api /repos/anthropics/skills/contents/{skill-name}/SKILL.md --jq '.content' | base64 -d"
)
```

**Store findings in basic-memory** for future reference:

```python
mcp_basic_memory_write_note(
    title="community-skill-{name}-{date}",
    directory="research/skills",
    content="## Source\n{url}\n\n## Summary\n{what it does}\n\n## Adaptation notes\n{what to change for cv-builder}"
)
```

## Step 2: Gap Analysis

Before creating a new skill, check if existing steering already covers the workflow. A skill that duplicates steering content adds maintenance burden without benefit.

**Check existing steering**:

```python
Bash (grep/rg)(
    pattern="{workflow keyword}",
    path=".claude/rules/",
    include="**/*.md"
)
```

**Check existing skills**:

```python
Bash (ls)(path=".claude/skills", depth=2)
```

**Decision rule**: if the user would explicitly say "do the X workflow", it's a skill. If the agent should follow the pattern automatically without being asked, it's steering.

**If steering already covers it**: consider updating the steering file with better examples rather than creating a new skill.

Full Skill-vs-Steering decision table + category guide live in `.claude/skills/skill-creator/references/skill-quality-checklist.md`.

## Step 3: Design the SKILL.md

Plan the skill structure before writing. Answer these questions:

1. **What is the skill's single purpose?** (one sentence)
2. **Who activates it?** (user explicitly, or agent automatically?)
3. **What are the 5+ trigger phrases?** (how would a user ask for this?)
4. **What are the 3+ activation examples?** (concrete queries)
5. **What category?** (planning / quality / security / testing / deployment / meta / domain-specific)
6. **What complexity?** (1=trivial, 2=simple, 3=moderate, 4=complex, 5=major)

**Frontmatter template**:

```yaml
---
name: {skill-name}
description: "{One-sentence summary of what the skill does}. Use when {primary use cases}. Activates on: {trigger phrase 1}, {trigger phrase 2}, {trigger phrase 3}, {trigger phrase 4}, {trigger phrase 5}, {trigger phrase 6}."
metadata:
  category: {category}
  complexity: {1-5}
  activation_examples:
    - "{concrete query 1 — natural language}"
    - "{concrete query 2 — natural language}"
    - "{concrete query 3 — natural language}"
---
```

**Name rules**:
- Lowercase, numbers, hyphens only
- Max 64 characters
- Must match the folder name exactly
- Descriptive but concise: `doc-coauthoring`, `webapp-testing`, `mcp-builder`

**Description rules** (hard limits — verified by `scripts/verify-skill-quality.py`):
- Max 1024 characters (truncation silently breaks matching)
- Must contain "Activates on:" with ≥5 trigger phrases
- Must be ≥100 words for reliable semantic matching

Full rules + measurement recipes: `.claude/skills/skill-creator/references/skill-quality-checklist.md`.

## Step 4: Write the Body

The body is the most important part. Thin skills that are just bullet points don't help agents — they need actual workflow steps with tool calls and examples.

**Body structure template**:

```markdown
# {Skill Name} Skill

{One paragraph describing what the skill does, where it comes from (if adapted), and when to use it.}

## When to Activate

- {Specific trigger condition 1}
- {Specific trigger condition 2}
- {Specific trigger condition 3}

## Step 1: {First Step Name}

{Explanation of what this step does and why.}

```python
# Actual tool call with real parameters
Read(path="path/to/relevant/file.py")
```

{What to look for in the output. What decisions to make.}

## Step 2: {Second Step Name}

...

## cv-builder-Specific Patterns

{Patterns specific to the cv-builder codebase that the skill should follow.}
```

**Content quality requirements**:

- Each step must have at least one actual tool call with real parameters
- Include concrete examples, not just descriptions
- Reference cv-builder-specific context: ADRs, tool names, project conventions
- Show what good output looks like, not just what to do
- Include error cases and how to handle them

Current tool-name patterns + anti-patterns (deprecated `readFile`/`executePwsh`/`pip`/`npm`/`black`/`terraform`) are catalogued in `.claude/skills/skill-creator/references/skill-quality-checklist.md`.

## Step 5: Quality Checklist

The full 6-section checklist (frontmatter, content, sub-files policy, structure, tool calls, anti-patterns, category guide) lives in `.claude/skills/skill-creator/references/skill-quality-checklist.md`.

Load it with Read when authoring a skill. The critical guardrails:

- [ ] `name` matches folder name exactly, ≤64 chars, lowercase-numbers-hyphens
- [ ] `description` ≤1024 chars, ≥100 words, contains `Activates on:` with ≥5 triggers
- [ ] `metadata` block with `category`, `complexity`, ≥3 `activation_examples`
- [ ] Content is substantive — workflow steps with real tool calls, not bullet points
- [ ] Sub-files policy: `references/*.md` flat + `scripts/*.{py,sh}` + `assets/*` allowed in workspace skills. Global skills (`~/.claude/skills/`) cannot use sub-files (Kiro bug #6955).

## Step 6: Verify

Run the quality-check script to verify all skills pass:

```bash
python3 .claude/skills/skill-creator/scripts/verify-skill-quality.py
```

Exit code 0 = all pass, 1 = issues found, 2 = tool error. The script checks every skill in `.claude/skills/` by default; pass a specific directory to check one.

Then run the full config validation suite:

```python
Bash(
    command="uv run --directory .claude/mcp --package verifai-kiro-checks validate-config"
)
```

## cv-builder-Specific Patterns

### Workspace scope

Skills live in `.claude/skills/{name}/SKILL.md`. The folder name must match the `name` field in frontmatter exactly.

```
.claude/skills/
├── doc-coauthoring/
│   └── SKILL.md
├── webapp-testing/
│   └── SKILL.md
└── {new-skill}/
    └── SKILL.md   ← name: {new-skill} in frontmatter
```

### Sub-files policy

**ALLOWED** for workspace skills at `.claude/skills/{name}/`:
- `references/*.md` (flat, no nesting)
- `scripts/*.{py,sh}`
- `assets/*`

**REQUIRED when using sub-files**:
- SKILL.md cites **absolute paths**: `.claude/skills/{name}/references/foo.md`
- SKILL.md body stays <500 lines (soft cap per Anthropic progressive-disclosure guidance)

**PROHIBITED**:
- Global skills at `~/.claude/skills/` with `references/` (Kiro bug #6955)
- Nested references (`references/foo/bar.md`)
- Non-markdown in `references/` (move scripts to `scripts/`, binaries to `assets/`)

### Commit to .claude/ repo

Skills are part of the `.claude/` configuration layer. Commit with a conventional commit message:

```bash
git add .claude/skills/{skill-name}/SKILL.md
git commit -m "feat(.claude): add {skill-name} skill"
```

Do NOT commit skills to the main cv-builder repository — they belong in the `.claude/` configuration layer only.

### Adapting community skills

When adapting a community skill for cv-builder:

1. **British English**: change American spellings (color → colour, organization → organisation, analyze → analyse)
2. **Tool names**: replace generic tool names with current Claude Code names (Read, Write, Edit, Bash) and cv-builder MCP prefixes (`mcp__basic-memory__*`, `mcp__basic-memory__*`, `mcp__exa__*`, `mcp__context7__*`)
3. **Project conventions**: `uv` not `pip`, `pnpm` not `npm`/`yarn`, `ruff` not `black`/`flake8`, `cdk` not `terraform`/`tofu`
4. **Attribution**: note the source in the skill's introduction paragraph
5. **ADR cross-links**: add links to relevant ADRs in `docs/adrs/` where the skill touches architectural decisions

Full adaptation guide + British-English word list: `.claude/skills/skill-creator/references/skill-quality-checklist.md`.
