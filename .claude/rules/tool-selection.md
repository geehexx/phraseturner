# Tool Selection

Decision tree for research/retrieval.

| Question type | Tool | Rationale |
|---|---|---|
| "Have we researched this before?" | `mcp__basic-memory__search_notes` | Prior research first |
| "What does our code do today?" | Grep / Glob / Read | Truth is in the repo |
| "How does library X do Y?" | Context7 resolve → query | Designed for library docs |
| "Current state of the web?" | Exa web_search | Semantic + recency filters |
| "Fetch a specific URL" | WebFetch | Known-good URL |
| "Multi-source synthesis" | Exa deep (≤1 call) | Expensive, last resort |

## Cost-tier ladder (fast/cheap first)

- **Tier 1** (free): basic-memory, Grep on `docs/`, local Read
- **Tier 2** (free, rate-limited): Context7 `resolve-library-id` → `query-docs`
- **Tier 3** ($0.007): Exa web_search
- **Tier 4** ($0.001): Exa web_fetch (known URL)
- **Tier 5** ($0.012): Exa deep (≤1 call per topic)

## Circuit breakers

Stop searching when:
- A decision in `docs/decisions/` or basic-memory answers the question.
- Context7 returned ≥3 relevant examples.
- Two independent sources agree.
- 3 Exa calls on the same topic.

## Anti-patterns

- Bash `curl` when WebFetch suffices — WebFetch is tracked.
- WebFetch on GitHub URLs — use `gh` CLI or GitHub MCP.
- Skipping the prior-research check.
- Not pinning library IDs (wastes a resolve call every time).

## Memory write-back

```yaml
---
title: <title>
type: note
permalink: research/<slug>
tags: [<domain>, <category>]
---

# Observations
- [finding] <fact> #tag1
- [decision] Chose X over Y because Z

# Relations
- related_to [[<other note>]]
```

Categories: `finding | decision | pattern | risk | metric | benchmark | constraint`.
Where to write: research → `research/<slug>`, decisions → `decisions/{YYYY-MM-DD}-<slug>`, context → `context/{YYYY-MM-DD}-<slug>` (7d TTL).
