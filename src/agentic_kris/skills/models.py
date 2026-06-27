"""Data model for a Skill, following Anthropic's SKILL.md convention.

A Skill is a *folder* containing a ``SKILL.md`` file with YAML frontmatter
(required ``name`` + ``description``) and a Markdown body of instructions. It may
bundle extra resources (reference docs) and executable ``scripts/``.

Progressive disclosure is modelled here:
  * level 1 — ``name`` + ``description`` (cheap metadata, always available),
  * level 2 — :meth:`Skill.body` (the SKILL.md instructions, read on demand),
  * level 3 — :attr:`resources` / :attr:`scripts` (loaded/run only when used).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class Skill:
    name: str
    description: str
    path: Path                       # the skill folder
    _body: str = ""                  # SKILL.md body (after frontmatter)
    metadata: Dict[str, object] = field(default_factory=dict)
    resources: List[Path] = field(default_factory=list)   # bundled reference files
    scripts: List[Path] = field(default_factory=list)     # bundled executables

    # ── level-1 view (metadata only) ─────────────────────────────────────────
    def catalog_entry(self) -> Dict[str, str]:
        """The cheap metadata an orchestrator/agent sees before deciding to use it."""
        return {"name": self.name, "description": self.description}

    # ── level-2 view (instructions) ──────────────────────────────────────────
    @property
    def body(self) -> str:
        """The SKILL.md instruction text (without frontmatter)."""
        return self._body

    def prompt_block(self) -> str:
        """Render this skill's instructions for injection into an agent prompt."""
        return f"## Skill: {self.name}\n{self._body.strip()}\n"

    # ── level-3 helpers (resources / scripts) ────────────────────────────────
    def resource(self, filename: str) -> Optional[Path]:
        for p in self.resources:
            if p.name == filename:
                return p
        return None

    def script(self, filename: str) -> Optional[Path]:
        for p in self.scripts:
            if p.name == filename:
                return p
        return None
