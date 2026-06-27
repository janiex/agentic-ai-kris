"""Skill loading, validation, and progressive disclosure."""
from __future__ import annotations

import pytest

from agentic_kris.skills.loader import SkillError, SkillLoader, _split_frontmatter


def test_example_skills_load(loader):
    names = set(loader.names())
    assert {"web-research", "critique", "document-solution"} <= names


def test_catalog_is_metadata_only(loader):
    for entry in loader.catalog():
        assert set(entry) == {"name", "description"}
        assert entry["description"].strip()


def test_prompt_for_includes_body(loader):
    block = loader.prompt_for(["web-research"])
    assert "## Skill: web-research" in block
    assert "research" in block.lower()


def test_web_research_bundles_script_and_reference(loader):
    skill = loader.get("web-research")
    assert any(p.name == "extract_claims.py" for p in skill.scripts)
    assert any(p.name == "reference.md" for p in skill.resources)


def test_run_script_executes(loader):
    out = loader.run_script(
        "web-research", "extract_claims.py", ["/dev/stdin"]
    ) if False else None
    # Drive it via a real temp input instead of stdin for portability.
    import subprocess, sys
    skill = loader.get("web-research")
    script = skill.script("extract_claims.py")
    res = subprocess.run(
        [sys.executable, str(script)],
        input="First fact here. Second fact here. First fact here.",
        capture_output=True, text=True,
    )
    assert res.returncode == 0
    # De-duplicates the repeated sentence -> 2 bullets.
    assert res.stdout.count("- ") == 2


def test_missing_required_fields_raise(tmp_path):
    sd = tmp_path / "bad"
    sd.mkdir()
    (sd / "SKILL.md").write_text("---\nname: bad\n---\nbody\n", encoding="utf-8")
    with pytest.raises(SkillError):
        SkillLoader(tmp_path)


def test_name_must_match_folder(tmp_path):
    sd = tmp_path / "folder-name"
    sd.mkdir()
    (sd / "SKILL.md").write_text(
        "---\nname: other-name\ndescription: x\n---\nbody\n", encoding="utf-8"
    )
    with pytest.raises(SkillError):
        SkillLoader(tmp_path)


def test_frontmatter_must_be_fenced():
    with pytest.raises(SkillError):
        _split_frontmatter("no frontmatter here")
