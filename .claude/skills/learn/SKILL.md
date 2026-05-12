---
name: learn
description: "Creates persistent learning guides from web research and codebase analysis. Stores structured knowledge in basic-memory for cross-session retrieval. Different from researcher agent — learn creates reusable reference guides, not one-shot research. Use when you want to document a pattern, library, or workflow for future sessions. Ideal after completing research that should be reusable across multiple agents and sessions. Produces structured notes with observations, relations, and tags for semantic search. Covers cv-builder-specific domains: PydanticAI agents, Nova Act scraper patterns, LanceDB semantic cache, RenderCV PDF output, ATS keyword scoring, and Hypothesis PBT. Activates on: create learning guide, document this pattern, save this knowledge, learn about, create reference guide, knowledge base entry, persist this research, build knowledge base, document how this works, save for later, store findings."
metadata:
  category: meta
  complexity: 2
  activation_examples:
    - "create a learning guide for the RRF fusion algorithm"
    - "document the EmbeddingService singleton pattern for future reference"
    - "learn about Nova Act stealth mode and save it"
    - "create a reference guide for the cv-builder CDK deployment patterns"
    - "save this knowledge about the ATS scoring rubric"
  related_steering:
    - tool-selection
    - research-workflow
---

# Learn

Creates persistent, reusable learning guides from web research and codebase analysis. Stores structured knowledge in basic-memory for cross-session retrieval.

## Difference from the Researcher Agent

The `researcher` agent produces one-shot research for a specific task. The `learn` skill creates **reusable reference guides** that persist across sessions and can be retrieved by any agent via `mcp_basic_memory_search_notes`. Use `learn` when you want the knowledge to be available in future sessions, not just the current one.

## When to Use

- Documenting a complex algorithm or pattern for future reference (SLOP detection heuristics, RenderCV YAML shape)
- Saving research findings that took significant effort to produce
- Creating a reference guide for a cv-builder-specific pattern (CDK deployment, EmbeddingService singleton)
- After discovering a non-obvious gotcha that future agents should know about
- Building up the knowledge base before a major feature implementation

## Step 1 — Research the Topic

Always check existing knowledge before researching from scratch:

```python
# 1. Check basic-memory first (free, instant)
mcp_basic_memory_search_notes(query="{topic keywords}")
mcp_basic_memory_search_notes(query="{related topic}")

# 2. Check ADRs for architectural decisions
Bash (grep/rg)(pattern="{topic}", path="docs/adrs", include="**/*.md")

# 3. Check the codebase for existing implementations
Bash (grep/rg)(pattern="{class or function name}", path="backend/src")
Bash (grep for symbol)(name="{SymbolName}")

# 4. Check docs/
Bash (grep/rg)(pattern="{topic}", path="docs", include="**/*.md")

# 5. Web research (only if steps 1-4 are insufficient)
mcp_basic_memory_search_notes(query="{topic} research")  # Check if already researched
remote_web_search(query="{topic} {specific aspect}")
mcp_exa_web_search_exa(query="{topic} documentation examples")
```

**Circuit breaker**: If basic-memory already has a comprehensive note on this topic (>500 words, recent), update it rather than creating a duplicate.

## Step 2 — Structure the Knowledge

Organise findings into a reusable reference format:

```markdown
# {Topic Name}

## What It Is
One paragraph explaining the concept clearly. No jargon without definition.

## How It Works
Technical explanation with the key mechanism. Include:
- The core algorithm or pattern
- Data flow (input → process → output)
- Key parameters and their effects

## When to Use It
- Scenario A: {description}
- Scenario B: {description}
- NOT when: {anti-use-cases}

## cv-builder Implementation
How this is used specifically in cv-builder:
- File location: {path}
- Key class/function: {name}
- ADR reference: {ADR-XXXX if applicable}

## Code Example
```python
# Concrete example from the cv-builder codebase
```

## Gotchas and Pitfalls
- {Gotcha 1}: {explanation and fix}
- {Gotcha 2}: {explanation and fix}

## References
- ADR-XXXX: {title}
- {file path}: {description}
- {URL}: {description}
```

## Step 3 — Write to basic-memory

```python
# Write the learning guide
mcp_basic_memory_write_note(
    title="{topic}-guide",
    directory="knowledge",
    content="""
# {Topic Name}

[structured content from Step 2]

## Observations
- [finding] {key finding 1}
- [finding] {key finding 2}
- [pattern] {reusable pattern}
- [limitation] {known limitation}
- [workaround] {workaround for limitation}
""",
    tags=["knowledge", "{domain}", "{topic}"]
)
```

**Naming convention**: `knowledge/{topic}-{date}` where date is `YYYY-MM-DD` from `Bash (date)()`.

**Content chunking**: If the guide is >3,500 characters, use `write_note` for the first chunk and `edit_note(operation="append")` for subsequent chunks.

## Step 4 — Add Relations to ADRs and Specs

Link the new note to relevant existing knowledge:

```python
# Add relations section to the note
mcp_basic_memory_edit_note(
    identifier="{topic}-guide",
    operation="append",
    content="""
## Relations
- implements [[ADR-XXXX]]
- relates-to [[{related-note-title}]]
- referenced-by [[{spec-name}]]
"""
)
```

**Observation taxonomy** (use these prefixes in the content):
- `[context]` — background information
- `[decision]` — a choice that was made
- `[preference]` — a preferred approach
- `[finding]` — a discovered fact
- `[limitation]` — a known constraint
- `[workaround]` — a fix for a limitation
- `[pattern]` — a reusable pattern

## cv-builder Knowledge Domains

Common topics worth creating learning guides for:

| Domain | Key Topics |
|--------|-----------|
| Scoring | ATS keyword extraction, SLOP detection, quantification gating |
| AI/ML | EmbeddingService singleton, ONNX inference, PydanticAI agents |
| Pipeline | PydanticAI output_validator + ModelRetry, Bedrock prompt caching |
| Infrastructure | CDK stack patterns, ECS deployment, Fargate CPU/memory constraints |
| Testing | Hypothesis strategies, LanceDB tmp-dir fixtures, pytest-benchmark |
| Kiro | Agent configuration, steering file patterns, hook architecture |

## Example: RRF Fusion Learning Guide

```python
mcp_basic_memory_write_note(
    title="rrf-fusion-guide",
    directory="knowledge",
    content="""
# Reciprocal Rank Fusion (RRF)

## What It Is
RRF is a rank aggregation algorithm that combines multiple ranked lists into a
single unified ranking. cv-builder uses it to fuse BM25 (keyword) and vector
(semantic) search results (ADR-0037).

## How It Works
Score formula: RRF(d) = Σ 1/(k + rank(d))
- k=60 is the standard constant (reduces sensitivity to top-ranked documents)
- rank(d) is the document's position in each ranked list (0-indexed)
- Higher RRF score = better combined rank

## cv-builder Implementation
- File: backend/src/cv_builder/search/services.py
- Function: _rrf_fusion()
- Config: SearchSettings.rrf_k (default 60)

## Gotchas
- [limitation] Documents not in a list get rank=infinity (score=0) — not penalised
- [workaround] Use a floor rank for missing documents to avoid score collapse
- [finding] k=60 is optimal for most cases; Optuna sweep confirmed this for cv-builder

## Relations
- implements [[ADR-0037]]
""",
    tags=["knowledge", "search", "rrf", "ranking"]
)
```

## References

- `tool-selection.md §10` — Note format, observation taxonomy, relation syntax
- `research-workflow.md` — Web research patterns and tool hierarchy
- `mcp_basic_memory_search_notes` — Retrieve stored knowledge
- `mcp_basic_memory_build_context` — Deep context retrieval with related notes
