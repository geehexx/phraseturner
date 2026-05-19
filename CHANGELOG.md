# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1](https://github.com/geehexx/phraseturner/compare/v0.2.0...v0.2.1) (2026-05-19)


### Documentation

* **contributing:** improve opener tone — remove informal greeting ([b09796f](https://github.com/geehexx/phraseturner/commit/b09796f5050341e41462b8f2a0dcdceeece8c546))

## [Unreleased]

## [0.1.0] - 2026-04-16

### Added

- FastMCP 3.0+ server with 7 MCP tools: `analyze`, `score`, `compare`, `list_personas`, `get_persona`, `create_persona`, `validate_persona`
- 5-dimension health scoring: readability, naturalness, vocabulary, semantic_preservation, tone_compliance
- 9 built-in personas: slack-casual, pr-review, confluence-docs, jira-ticket, email-professional, blog-post, technical-docs, executive-summary, internal-references
- FLAN-T5-base INT8 ONNX integration for sentence-level style, tone, and persona compliance analysis
- 4-tier persona directory system (project → user → remote → built-in)
- Hot-reload of persona YAML files via watchfiles
- Semantic persona search via FastEmbed bge-small-en-v1.5
- Vale-compatible YAML rule system with 10 rule types + 3 phraseturner extensions (llm_eval, tone, brand_voice)
- Persona validation with 12 structured error codes
- Gaussian decay readability scoring with channel-specific targets and score floor
- Async pipeline with parallel Stage 1 analyzers via asyncio.gather
- Graceful degradation: partial results with degraded=true when stages fail
- `next_steps` field on all tool responses via NextStepsBuilder
- 6-component tool description framework (purpose, constraints, side effects, usage, follow-up, errors)
- Structured error responses with machine-readable codes
- 743 tests with 91.65% coverage
- 25 correctness properties (round-trip, invariant, metamorphic, idempotence)
- mkdocs-material documentation site with API reference, persona guide, quickstart
- GitHub Actions CI with Python 3.12/3.13 matrix
- Pre-commit hooks: ruff, mypy, gitleaks, codespell

### Fixed

- Compare tool INTERNAL_ERROR caused by next_steps min_length constraint
- Content hygiene rule violations not surfaced as per-sentence flags
- Rule message '%s' placeholders replaced with actual matched text
- Generic suggestion hints replaced with actionable text
- PersonaDetail Any-typed fields replaced with concrete schema types
- First-call latency spike (lexicalrichness ~2s, scipy.stats ~1.6s) via pre-import at startup
