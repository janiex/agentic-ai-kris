"""Discover and load Anthropic-format Skills from a skills directory.

Each skill is a folder holding a ``SKILL.md`` file:

    skills/
      web-research/
        SKILL.md            # YAML frontmatter (name, description) + Markdown body
        reference.md        # optional bundled reference (level 3)
        scripts/extract.py  # optional bundled executable (level 3)

The loader enforces the guide's required frontmatter and exposes the three
progressive-disclosure levels. It is cross-platform: every path is a
``pathlib.Path`` and bundled scripts run via ``sys.executable``.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from .models import Skill

# Folders inside a skill package that hold runnable scripts (level 3).
_SCRIPT_DIRS = ("scripts",)
# A reasonable cap mirroring the guide's "keep SKILL.md focused" rule.
_NAME_MAX_LEN = 64


class SkillError(ValueError):
    """Raised when a SKILL.md is malformed or violates the authoring rules."""


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body) from a SKILL.md string.

    Frontmatter is a leading ``---`` fenced YAML block, per the convention.
    """
    if not text.lstrip().startswith("---"):
        raise SkillError("SKILL.md must begin with a '---' YAML frontmatter block.")
    stripped = text.lstrip()
    # Split on the closing fence: ---\n<yaml>\n---\n<body>
    parts = stripped.split("---", 2)
    if len(parts) < 3:
        raise SkillError("SKILL.md frontmatter is not closed with a second '---'.")
    front = yaml.safe_load(parts[1]) or {}
    if not isinstance(front, dict):
        raise SkillError("SKILL.md frontmatter must be a YAML mapping.")
    body = parts[2].lstrip("\n")
    return front, body


def _validate(front: dict, folder: str) -> None:
    name = front.get("name")
    desc = front.get("description")
    if not name or not isinstance(name, str):
        raise SkillError(f"Skill '{folder}': frontmatter 'name' is required.")
    if not desc or not isinstance(desc, str):
        raise SkillError(f"Skill '{folder}': frontmatter 'description' is required.")
    if len(name) > _NAME_MAX_LEN:
        raise SkillError(f"Skill '{folder}': 'name' exceeds {_NAME_MAX_LEN} chars.")
    if name != name.lower() or " " in name:
        raise SkillError(
            f"Skill '{folder}': 'name' must be lowercase and hyphenated (got {name!r})."
        )
    if name != folder:
        raise SkillError(
            f"Skill folder '{folder}' must match frontmatter name '{name}'."
        )


def _parse_skill(skill_dir: Path) -> Skill:
    md = skill_dir / "SKILL.md"
    front, body = _split_frontmatter(md.read_text(encoding="utf-8"))
    _validate(front, skill_dir.name)

    scripts: List[Path] = []
    for sub in _SCRIPT_DIRS:
        d = skill_dir / sub
        if d.is_dir():
            scripts.extend(sorted(p for p in d.iterdir() if p.is_file()))

    # Any other file alongside SKILL.md is a bundled reference resource.
    resources = sorted(
        p
        for p in skill_dir.iterdir()
        if p.is_file() and p.name != "SKILL.md"
    )

    return Skill(
        name=front["name"],
        description=front["description"],
        path=skill_dir,
        _body=body,
        metadata=front.get("metadata", {}) or {},
        resources=resources,
        scripts=scripts,
    )


class SkillLoader:
    """Loads, caches, and serves skills from a directory."""

    def __init__(self, skills_dir: Path):
        self.skills_dir = Path(skills_dir)
        self._skills: Dict[str, Skill] = {}
        self.reload()

    def reload(self) -> None:
        self._skills.clear()
        if not self.skills_dir.is_dir():
            return
        for entry in sorted(self.skills_dir.iterdir()):
            if entry.is_dir() and (entry / "SKILL.md").is_file():
                skill = _parse_skill(entry)
                self._skills[skill.name] = skill

    # ── level-1: metadata catalog ────────────────────────────────────────────
    def catalog(self) -> List[Dict[str, str]]:
        """All skills as cheap {name, description} entries (progressive level 1)."""
        return [s.catalog_entry() for s in self._skills.values()]

    def names(self) -> List[str]:
        return list(self._skills)

    # ── level-2: full skill (instructions) ───────────────────────────────────
    def get(self, name: str) -> Skill:
        if name not in self._skills:
            raise KeyError(f"Unknown skill: {name!r}. Available: {self.names()}")
        return self._skills[name]

    def get_many(self, names: List[str]) -> List[Skill]:
        return [self.get(n) for n in names if n in self._skills]

    def prompt_for(self, names: List[str]) -> str:
        """Concatenate the instruction blocks of the named skills for a prompt."""
        blocks = [self.get(n).prompt_block() for n in names if n in self._skills]
        return "\n".join(blocks)

    # ── level-3: run a bundled script ────────────────────────────────────────
    def run_script(
        self, skill_name: str, script: str, args: Optional[List[str]] = None,
        timeout: int = 60,
    ) -> str:
        """Execute a bundled, deterministic helper script and return its stdout.

        Uses ``sys.executable`` rather than a hardcoded ``python3`` so it runs
        identically on Linux, macOS, and Windows.
        """
        skill = self.get(skill_name)
        path = skill.script(script)
        if path is None:
            raise FileNotFoundError(
                f"Skill {skill_name!r} has no script {script!r}."
            )
        result = subprocess.run(
            [sys.executable, str(path), *(args or [])],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Script {script!r} failed (exit {result.returncode}): {result.stderr.strip()}"
            )
        return result.stdout
