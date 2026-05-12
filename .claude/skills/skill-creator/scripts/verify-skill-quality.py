#!/usr/bin/env python3
"""Verify all SKILL.md files in .claude/skills/ pass quality checks.

Two severity levels:
- FAIL: genuine breakage (invalid YAML, name mismatch, description too long).
  The skill is either broken or will silently fail to match. Exit code 1.
- WARN: cv-builder-convention nudge (missing metadata block, short description).
  The skill works but doesn't follow our house style. Does not affect exit code
  in default mode. Use --strict to treat WARN as FAIL.

Usage:
    python3 .claude/skills/skill-creator/scripts/verify-skill-quality.py
    python3 .claude/skills/skill-creator/scripts/verify-skill-quality.py <skill-dir>
    python3 .claude/skills/skill-creator/scripts/verify-skill-quality.py --strict
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml not installed. Run: uv pip install pyyaml")
    sys.exit(2)


# Anthropic spec hard requirements (see
# platform.claude.com/docs/en/docs/agents-and-tools/agent-skills/best-practices):
# - name: lowercase letters/numbers/hyphens, ≤64 chars, must match folder name
# - description: ≤1024 chars
# Everything else is cv-builder convention; WARN not FAIL.

MIN_DESC_WORDS = 50           # Practical floor; actual Anthropic guidance is ≥100
MIN_TRIGGERS = 3              # cv-builder adds "Activates on:" pattern
SKILL_BODY_SOFT_CAP_LINES = 500  # Anthropic progressive-disclosure guidance


def check_skill(skill_dir: Path) -> tuple[list[str], list[str]]:
    """Return (fails, warns)."""
    fails: list[str] = []
    warns: list[str] = []
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.exists():
        return ["missing SKILL.md"], []

    content = skill_file.read_text()
    if not content.startswith("---"):
        return ["missing frontmatter"], []

    try:
        fm_end = content.index("---", 3)
        fm = yaml.safe_load(content[3:fm_end])
    except Exception as e:
        return [f"invalid YAML: {e}"], []

    name = fm.get("name", "")
    desc = fm.get("description", "")
    meta = fm.get("metadata", {})

    # FAIL checks — genuine breakage
    if name != skill_dir.name:
        fails.append(f"name mismatch: {name!r} != {skill_dir.name!r}")
    if len(desc) > 1024:
        fails.append(f"description too long: {len(desc)} chars (Anthropic max 1024)")

    # WARN checks — cv-builder convention nudges
    if len(desc.split()) < MIN_DESC_WORDS:
        warns.append(f"description short: {len(desc.split())} words (suggested min {MIN_DESC_WORDS})")
    if "Activates on:" not in desc:
        warns.append('missing "Activates on:" in description')
    else:
        triggers = [t.strip() for t in desc.split("Activates on:")[1].split(",") if t.strip()]
        if len(triggers) < MIN_TRIGGERS:
            warns.append(f"few triggers: {len(triggers)} (suggested min {MIN_TRIGGERS})")

    if not meta:
        warns.append("no metadata block (cv-builder convention)")
    else:
        # If metadata exists, enforce its shape
        if "category" not in meta:
            warns.append("metadata.category missing")
        if "complexity" not in meta:
            warns.append("metadata.complexity missing")
        examples = meta.get("activation_examples", [])
        if len(examples) < 3:
            warns.append(f"activation_examples: {len(examples)} (suggested min 3)")

    # Sub-files policy — FAIL on genuine violations
    refs_dir = skill_dir / "references"
    if refs_dir.exists():
        for ref in refs_dir.iterdir():
            if ref.is_dir():
                fails.append(f"nested references/{ref.name}/ prohibited (progressive-disclosure previews miss content)")
            elif ref.suffix != ".md":
                fails.append(f"non-markdown in references/: {ref.name}")
        body_lines = content.count("\n") + 1
        if body_lines >= SKILL_BODY_SOFT_CAP_LINES:
            warns.append(
                f"SKILL.md {body_lines} lines with references/ "
                f"(Anthropic soft cap {SKILL_BODY_SOFT_CAP_LINES})"
            )

    return fails, warns


def main(argv: list[str]) -> int:
    strict = "--strict" in argv
    argv = [a for a in argv if a != "--strict"]

    if len(argv) > 1:
        target = Path(argv[1])
        skills_to_check = [target] if target.is_dir() else []
        if not skills_to_check:
            print(f"ERROR: {target} is not a directory")
            return 2
    else:
        skills_dir = Path(".claude/skills")
        if not skills_dir.exists():
            print(f"ERROR: {skills_dir} not found. Run from repo root.")
            return 2
        skills_to_check = sorted(d for d in skills_dir.iterdir() if d.is_dir())

    passed: list[str] = []
    failed_skills: list[str] = []
    warned_skills: list[str] = []
    all_fails: list[str] = []
    all_warns: list[str] = []

    for skill_dir in skills_to_check:
        fails, warns = check_skill(skill_dir)
        if fails:
            failed_skills.append(skill_dir.name)
            for issue in fails:
                all_fails.append(f"  FAIL {skill_dir.name}: {issue}")
        if warns:
            warned_skills.append(skill_dir.name)
            for issue in warns:
                all_warns.append(f"  WARN {skill_dir.name}: {issue}")
        if not fails and not warns:
            passed.append(skill_dir.name)

    total = len(skills_to_check)
    print(f"Checked: {total} skills")
    print(f"  Clean:  {len(passed)}")
    print(f"  FAIL:   {len(failed_skills)} skills, {len(all_fails)} issues")
    print(f"  WARN:   {len(warned_skills)} skills, {len(all_warns)} issues")

    if all_fails:
        print("\nFailures:")
        for line in all_fails:
            print(line)

    if all_warns:
        print("\nWarnings:")
        for line in all_warns:
            print(line)

    if all_fails:
        return 1
    if strict and all_warns:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
