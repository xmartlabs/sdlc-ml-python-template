"""Harness levels (ADR-0003): a project carries ``minimal`` or ``full``."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from ml_python_base.skills_sync.cli import check_drift, main
from ml_python_base.skills_sync.config import load_registry
from ml_python_base.skills_sync.discovery import discover_skills
from ml_python_base.skills_sync.levels import (
    FULL,
    LevelError,
    Selection,
    carried_names,
    load_levels,
    load_selection,
    write_selection,
)
from ml_python_base.skills_sync.models import Skill, SkillMeta

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "adapters/registry.toml"
MINIMAL = {
    "brainstorm_quick",
    "plan_and_execute_feature",
    "requesting-code-review",
    "research_current_info",
    "systematic_debugging",
    "verify_changes",
    "writing-plans",
}
ADAPTERS = (
    "CLAUDE.md",
    "AGENTS.md",
    "OPENCODE.md",
    ".agents/rules/GEMINI.md",
    ".github/copilot-instructions.md",
)
NATIVE_VIEWS = (".claude/skills", ".codex/skills", ".opencode/skills", ".agents/skills")


def _skill(name: str, *, legacy: bool = False) -> Skill:
    return Skill(
        name=name,
        kind="internal",
        source_path=Path(f"{name}.md"),
        meta=SkillMeta(visibility="legacy" if legacy else "internal"),
    )


def _write_levels(root: Path, body: str) -> None:
    (root / ".github").mkdir(parents=True, exist_ok=True)
    (root / ".github/harness-levels.toml").write_text(body, encoding="utf-8")


# --------------------------------------------------------------------------
# Level definitions and the project's selection
# --------------------------------------------------------------------------


def test_the_governed_levels_are_minimal_and_full() -> None:
    levels = load_levels(REPO_ROOT)
    assert set(levels) == {FULL, "minimal"}
    assert levels[FULL].skills is None
    assert levels["minimal"].skills == MINIMAL


def test_minimal_names_only_live_skills() -> None:
    registry = load_registry(REGISTRY_PATH)
    live = {
        s.name
        for s in discover_skills(REPO_ROOT, registry=registry)
        if not s.meta.is_legacy
    }
    assert live >= MINIMAL


def test_extends_composes_and_include_exclude_adjust(tmp_path: Path) -> None:
    _write_levels(
        tmp_path,
        '[level.base]\nskills = ["a"]\n[level.wide]\nextends = "base"\nskills = ["b"]\n',
    )
    levels = load_levels(tmp_path)
    assert levels["wide"].skills == {"a", "b"}
    skills = [_skill(n) for n in ("a", "b", "c")]
    picked = carried_names(
        skills,
        levels,
        Selection(level="wide", include=("c",), exclude=("a",), source="x"),
    )
    assert picked == {"b", "c"}


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ('[level.full]\nskills = ["a"]\n', "built in"),
        ('[level.a]\nextends = "full"\n', "cannot extend"),
        ('[level.a]\nextends = "ghost"\n', "unknown level"),
        ('[level.a]\nextends = "b"\n[level.b]\nextends = "a"\n', "cycle"),
    ],
)
def test_invalid_level_definitions_are_refused(
    tmp_path: Path, body: str, message: str
) -> None:
    _write_levels(tmp_path, body)
    with pytest.raises(LevelError, match=message):
        load_levels(tmp_path)


def test_unknown_level_or_skill_in_the_selection_is_refused(tmp_path: Path) -> None:
    _write_levels(tmp_path, '[level.minimal]\nskills = ["a"]\n')
    levels = load_levels(tmp_path)
    skills = [_skill("a")]
    with pytest.raises(LevelError, match="unknown level"):
        carried_names(skills, levels, Selection(level="tiny", source="harness.toml"))
    with pytest.raises(LevelError, match="Not a live skill: ghost"):
        carried_names(
            skills, levels, Selection(level="minimal", include=("ghost",), source="x")
        )


def test_no_harness_toml_selects_full(tmp_path: Path) -> None:
    selection = load_selection(tmp_path)
    assert selection.is_default and selection.level == FULL


def test_write_selection_round_trips(tmp_path: Path) -> None:
    write_selection(tmp_path, "minimal")
    selection = load_selection(tmp_path)
    assert (selection.level, selection.include, selection.exclude) == (
        "minimal",
        (),
        (),
    )


# --------------------------------------------------------------------------
# End to end against a copy of this template
# --------------------------------------------------------------------------


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A copy of this repository's governed and generated tree."""
    root = tmp_path / "project"
    ignore = shutil.ignore_patterns(
        ".git", ".venv", "__pycache__", "*.pyc", "node_modules"
    )
    shutil.copytree(REPO_ROOT, root, ignore=ignore, symlinks=True)
    return root


def _cli(root: Path, *args: str) -> int:
    return main(
        ["--root", str(root), "--registry", str(root / "adapters/registry.toml"), *args]
    )


def _region(text: str) -> str:
    return text[
        text.index("BEGIN GENERATED SKILLS") : text.index("END GENERATED SKILLS")
    ]


def _entries(view: Path) -> set[str]:
    return {p.name for p in view.iterdir() if not p.name.startswith(".")}


def test_minimal_carries_seven_skills_everywhere(project: Path) -> None:
    assert _cli(project, "level", "--set", "minimal") == 0

    for view in NATIVE_VIEWS:
        assert _entries(project / view) == MINIMAL, view
    every = {
        s.name
        for s in discover_skills(project, registry=load_registry(REGISTRY_PATH))
        if not s.meta.is_legacy
    }
    for adapter in ADAPTERS:
        region = _region((project / adapter).read_text(encoding="utf-8"))
        named = set(re.findall(r"`([\w:-]+)`", region)) & every
        # No dangling routing: the adapter never names a skill not carried here.
        assert named <= MINIMAL, (adapter, sorted(named - MINIMAL))
    # Nothing was deleted: every skill is still in the governed sources.
    assert (project / ".github/skills/retrospective.md").is_file()
    assert (project / ".github/skills-external/test-driven-development").is_dir()
    assert check_drift(project, load_registry(project / "adapters/registry.toml")) == []


def test_minimal_makes_every_adapter_lighter(project: Path) -> None:
    before = {a: (project / a).stat().st_size for a in ADAPTERS}
    assert _cli(project, "level", "--set", "minimal") == 0
    for adapter in ADAPTERS:
        assert (project / adapter).stat().st_size < before[adapter], adapter


def test_include_switches_an_optional_skill_on(project: Path) -> None:
    write_selection(project, "minimal")
    selection = project / "harness.toml"
    selection.write_text(
        selection.read_text(encoding="utf-8").replace(
            "include = []", 'include = ["test-driven-development"]'
        ),
        encoding="utf-8",
    )
    assert _cli(project, "sync") == 0
    assert "test-driven-development" in _entries(project / ".claude/skills")


def test_full_restores_todays_output_byte_for_byte(project: Path) -> None:
    generated = (*ADAPTERS, "docs/generated/skills-catalog.md")
    original = {p: (project / p).read_bytes() for p in generated}
    assert _cli(project, "level", "--set", "minimal") == 0
    (project / "harness.toml").unlink()
    assert _cli(project, "sync") == 0
    for path in generated:
        assert (project / path).read_bytes() == original[path], path
    assert _cli(project, "level", "--set", FULL) == 0
    for path in generated:
        assert (project / path).read_bytes() == original[path], path


def test_a_stale_native_view_is_drift(project: Path) -> None:
    assert _cli(project, "level", "--set", "minimal") == 0
    registry = load_registry(project / "adapters/registry.toml")
    # Widen the selection without relinking: the views now miss a skill.
    write_selection(project, FULL)
    stale = check_drift(project, registry)
    assert any(path.startswith(".claude/skills/") for path in stale)


def test_governed_agents_bind_skills_present_in_the_sources() -> None:
    """Agents read their bound skills from .github/skills*/, present at any
    level — so a minimal project's agents never point at nothing."""
    names = {p.stem for p in (REPO_ROOT / ".github/skills").glob("*.md")} | {
        p.name for p in (REPO_ROOT / ".github/skills-external").iterdir()
    }
    for agent in (REPO_ROOT / ".github/agents").glob("*.md"):
        match = re.search(
            r"^skills:\s*\[(.*?)\]", agent.read_text(encoding="utf-8"), re.M
        )
        if not match:
            continue
        for bound in filter(None, (s.strip() for s in match.group(1).split(","))):
            assert bound in names, (agent.name, bound)
