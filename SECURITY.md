# Security Policy

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Use [GitHub Private Vulnerability Reporting](https://github.com/geehexx/phraseturner/security/advisories/new) to report security issues confidentially.

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 0.1.x   | ✅ Yes    |

## Security Controls

- Input validation on all text inputs (max 8,000 tokens, empty text rejection)
- Persona name sanitisation prevents path traversal (`^[a-z0-9][a-z0-9-]*$`)
- YAML parsing uses `yaml.safe_load()` only — no arbitrary code execution
- No network calls during analysis — all processing is local
- Secrets detection in persona YAML via `PersonaValidator._check_secrets()`
