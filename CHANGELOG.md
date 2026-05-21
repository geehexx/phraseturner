# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.1.0 (2026-05-21)


### Features

* **claude:** migrate from .kiro/ to Claude Code config layout ([#1](https://github.com/geehexx/phraseturner/issues/1)) ([e63d767](https://github.com/geehexx/phraseturner/commit/e63d76766331089d5ed3ada1b1f208b33e056df3))
* initial project scaffolding ([183d886](https://github.com/geehexx/phraseturner/commit/183d8862c82a79c5d8b1a381f0491b0a7c59be5a))
* **personas:** add agent-coordination personas (fork-brief, decision-note, panel-vote-dissent) ([32feee2](https://github.com/geehexx/phraseturner/commit/32feee2719e928674074dda5250bbd595b79ff8c))
* **personas:** add agent-coordination personas (fork-brief, decision-note, panel-vote-dissent) ([2641a45](https://github.com/geehexx/phraseturner/commit/2641a4585e278df7510dc683cf0928250a3ebb8f))


### Bug Fixes

* add exc_info=True to non-pipeline exception catches in tools.py and validation.py ([0bfd323](https://github.com/geehexx/phraseturner/commit/0bfd323b3bb6c37ed17aa1eb6b2299a37a58c9e4))
* **calibration:** share pipeline results across tests to prevent timeout ([d1dba74](https://github.com/geehexx/phraseturner/commit/d1dba74c9350978e8316a83f270081599c82236d))
* **naturalness:** guard zero-variance arrays before scipy skew call ([d1c089e](https://github.com/geehexx/phraseturner/commit/d1c089ea73c69c007df42621dd0ff6af7c9f50fb))
* **personas:** add fork-brief/decision-note/panel-vote channels to enum + fix raw fields ([2f4c856](https://github.com/geehexx/phraseturner/commit/2f4c8564daba4b6de9fdf03a815c61dc56eb167b))
* wire T5 results into pipeline, harden assert statements, add SECURITY.md and dependabot ([441e0b7](https://github.com/geehexx/phraseturner/commit/441e0b747d7170005c4ed0344d17251523853d7c))


### Documentation

* **contributing:** improve opener tone — remove informal greeting ([05c914e](https://github.com/geehexx/phraseturner/commit/05c914eb435f98b5ba08375fa4203e5d088a2c64))

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
